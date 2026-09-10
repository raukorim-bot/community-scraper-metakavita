#!/usr/bin/env python3
"""Campagne de validation live du catalogue, conçue pour ne pas faire bannir l'IP.

Ce runner est plus prudent que `run_live_smoke.py`, sur les points qui ont déjà
coûté un bannissement dans ce dépôt :

* **Cadence indexée sur l'HÔTE, pas sur le scraper.** `throttle_provider()` est
  indexé sur `scraper.id` : deux scrapers qui visent le même hôte gardent deux
  horloges pour un seul serveur, et celui-ci les reçoit à la somme des deux
  débits. C'est ce qui a fait retirer BDGEST. `www.googleapis.com` est
  aujourd'hui interrogé par GOOGLEBOOKS et par OPENLIBRARY. La cadence de la
  campagne s'ajoute donc à celle du scraper, indexée sur l'hôte.
* **Coupe-circuit par hôte.** Au premier 403 / 429 / 503 — ou au premier écran
  Cloudflare — l'hôte est retiré de la campagne. On ne réessaie jamais un hôte
  qui vient de dire non : insister est exactement ce qui transforme un refus
  ponctuel en bannissement.
* **Abandon global.** Au-delà de `--max-blocked` hôtes bloqués, toute la
  campagne s'arrête. Plusieurs hôtes qui refusent d'affilée ne signalent pas
  autant de sites en panne : ils signalent que c'est l'adresse de sortie qui
  est marquée. Continuer ne ferait qu'aggraver le marquage.
* **Reprise sur incident.** Chaque résultat est écrit au fil de l'eau. Relancer
  avec `--resume` ne réinterroge pas ce qui a déjà répondu — relancer une
  campagne complète pour récupérer trois lignes, c'est repayer tout le trafic.
* **Une requête de recherche par scraper**, sur des titres très populaires donc
  probablement déjà en cache côté site.
* **Les scrapers retirés ne sont jamais interrogés** : leur hôte est déjà
  couvert par une autre entrée du catalogue.

Usage (depuis le clone community, MetaKavita sur PYTHONPATH) :

    export PYTHONPATH=/chemin/vers/MetaKavita
    export METAKAVITA_ROOT=/chemin/vers/MetaKavita
    python tests/run_live_validation.py --dry-run      # plan, aucun trafic
    python tests/run_live_validation.py                # campagne complète
    python tests/run_live_validation.py --resume       # reprise après abandon
    python tests/run_live_validation.py --only BNF,DNB # un sous-ensemble

Sort 1 s'il reste des FAIL. BLOCKED / SKIP / EXPECTED ne comptent pas comme
des échecs : ce sont des verdicts sur l'environnement, pas sur le code.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import random
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MK = Path(os.environ.get("METAKAVITA_ROOT", r"Z:\kavitafetcher"))
for _p in (str(MK), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SKIP_FILES = {"debug_dump_ann.py", "debug_dump_planetebd.py", "debug_dump_fandom.py"}

# Codes par lesquels un site signale qu'il en a assez. Aucun n'est réessayé.
PUSHBACK = {401, 403, 405, 409, 429, 503}

# Parmi eux, ceux qui disent quelque chose de l'ADRESSE DE SORTIE — un refus,
# pas un compteur plein. Eux seuls alimentent l'abandon global.
#
# La distinction vient d'une campagne réelle : elle s'est arrêtée sur
# anilist.co 403 (Cloudflare refusant une IP datacenter), bdtheque.com 403
# (refus du site) et googleapis.com 429 (quota anonyme Google, partagé par
# tout le monde sur cette IP). Les additionner pour conclure « l'adresse est
# marquée » est un raccourci : un quota plein n'est pas un refus, il se vide
# tout seul, et il a interrompu une campagne qui se déroulait normalement.
# Un 429 retire quand même le domaine de la campagne — insister sur une API
# qui compte les appels est précisément ce qu'il ne faut pas faire.
REFUSALS = {401, 403, 405, 409, 503}

# Signatures d'un échec de TRANSPORT : la requête n'a jamais atteint le site.
# À ne surtout pas confondre avec un refus du site. Un refus est un verdict sur
# l'adresse de sortie ou sur le scraper ; un échec de transport ne dit rien du
# tout — ni du site, ni du code — et le rapporter comme une panne de scraper
# envoie chercher un bug qui n'existe pas. C'est le cas typique d'un proxy
# d'entreprise, d'un pare-feu de sortie ou d'un conteneur sans accès réseau.
TRANSPORT_FAILURES = (
    # Deux formulations pour un même échec : urllib3 dit « Tunnel connection
    # failed », curl_cffi dit « CONNECT tunnel failed ». N'en retenir qu'une
    # laissait passer la seconde dès qu'elle n'était pas enveloppée dans une
    # ConnectionError.
    "proxyerror", "tunnel connection failed", "connect tunnel failed",
    "failed to perform", "max retries exceeded",
    "connectionerror", "connecttimeout", "nameresolutionerror",
    "failed to resolve", "temporary failure in name resolution",
    "network is unreachable", "no route to host", "connection refused",
    "ssl", "certificate verify failed", "curlerror", "connection reset",
)


def is_transport_failure(err: str) -> bool:
    low = (err or "").casefold()
    return any(marker in low for marker in TRANSPORT_FAILURES)


# Marqueurs d'une interstitielle anti-bot dans un corps HTTP 200.
CF_MARKERS = (
    "just a moment",
    "checking your browser",
    "cf-browser-verification",
    "attention required! | cloudflare",
    "enable javascript and cookies to continue",
)

# Suffixes publics composés rencontrés ou plausibles pour ce catalogue. Sans
# eux, `ndlsearch.ndl.go.jp` se réduirait à `go.jp` — un suffixe public, pas un
# domaine. La liste n'a pas à être exhaustive : elle n'affecte que la finesse du
# regroupement, et se tromper la rend plus prudente, jamais moins.
COMPOUND_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "co.jp", "or.jp", "ne.jp", "go.jp",
    "ac.jp", "com.br", "com.au", "net.au", "org.au", "co.nz", "com.cn",
    "com.tw", "co.kr", "or.kr", "com.mx", "com.ar", "co.za", "com.tr",
}


def rate_key(host: str) -> str:
    """Domaine enregistrable d'un hôte — la clé de cadence et de coupe-circuit.

    Un quota et un bannissement s'appliquent à un site, pas à un nom d'hôte.
    `www.loc.gov`, `lccn.loc.gov`, `lx2.loc.gov` et `tile.loc.gov` sont la même
    Library of Congress derrière la même politique ; leur donner une horloge
    chacun, c'est quadrupler le débit réel vu par le serveur tout en croyant
    respecter la cadence. C'est la version par hôte de l'erreur qui a fait
    retirer BDGEST. Regrouper trop large ne fait que ralentir la campagne ;
    regrouper trop fin est ce qui fait bannir.
    """
    host = (host or "").lower().strip(".")
    parts = [p for p in host.split(".") if p]
    if len(parts) < 3:
        return ".".join(parts)
    if ".".join(parts[-2:]) in COMPOUND_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


KEY_ENV = {
    "METRON": "METRON_API_KEY",
    "ISBNDB": "ISBNDB_API_KEY",
    "NOVELUPDATES": "NOVELUPDATES_API_KEY",
    "GCD": "GCD_API_KEY",
    "COMICVINE": "COMICVINE_API_KEY",
    "HARDCOVER": "HARDCOVER_API_KEY",
    "MAL": "MAL_API_KEY",
    "GOOGLEBOOKS": "GOOGLEBOOKS_API_KEY",
}

# Clés facultatives : le scraper fonctionne sans, la clé ne fait que relever
# le quota. Absente, on tente quand même le live.
OPTIONAL_KEYS = {"NOVELUPDATES", "GCD", "GOOGLEBOOKS"}

REQUIRED_CAND_KEYS = {
    "title", "genres", "tags", "staff", "format", "alternative_titles",
}

# Une seule requête de recherche par scraper, sur un titre assez connu pour
# être déjà en cache côté site.
DEFAULT_QUERY = {
    "Manga": ("Death Note", "Manga"),
    "Comic": ("Watchmen", "Comic"),
    "Book": ("Le Petit Prince", "Book"),
}
QUERY_OVERRIDE = {
    "TAPAS": ("Solo Leveling", "Manga"),
    "WEBTOON": ("Tower of God", "Manga"),
    "GCD": ("Watchmen", "Comic"),
    "BNF": ("Les Misérables", "Book"),
    "DNB": ("Der Prozess", "Book"),
    "BNE": ("Don Quijote", "Book"),
    "SBN": ("Il nome della rosa", "Book"),
    "NDL": ("Norwegian Wood", "Book"),
    "KB": ("Max Havelaar", "Book"),
    "OPENBD": ("9784088725093", "Book"),
    "LOC": ("Moby Dick", "Book"),
    "PLANETEBD": ("Astérix", "Comic"),
    "BEDETHEQUE": ("Astérix", "Comic"),
    "BDTHEQUE": ("Astérix", "Comic"),
    "SENSCRITIQUE": ("Tintin", "Comic"),
    "TEBEOSFERA": ("Mortadelo", "Comic"),
    "LOCG": ("Watchmen", "Comic"),
    "MANGANEWS": ("Death Note", "Manga"),
    "FANDOM": ("Death Note", "Manga"),
    "ANN": ("Death Note", "Manga"),
    "BANGUMI": ("Death Note", "Manga"),
    "ANIMEPLANET": ("Death Note", "Manga"),
    "MANGASANCTUARY": ("Death Note", "Manga"),
    "BABELIO": ("Le Petit Prince", "Book"),
    "DECITRE": ("Le Petit Prince", "Book"),
}


# Ces trois signaux dérivent de `BaseException`, pas de `Exception`, et c'est
# délibéré. Presque tous les scrapers enveloppent leurs requêtes dans un
# `try: ... except Exception: continue` pour survivre à une page cassée. Un
# signal d'arrêt dérivé de `Exception` y serait donc avalé par le scraper
# lui-même : le coupe-circuit se déclencherait, le scraper l'ignorerait, et la
# boucle passerait à la requête suivante vers l'hôte qui vient de refuser —
# exactement le comportement que ce runner existe pour empêcher. `BaseException`
# traverse ces `except Exception` comme le fait `KeyboardInterrupt`.
class CampaignAbort(BaseException):
    """L'adresse de sortie semble marquée : on arrête tout."""


class HostRefused(BaseException):
    """L'hôte a déjà refusé : on ne le réinterroge pas."""


class BudgetExhausted(BaseException):
    """Plafond de requêtes atteint pour ce scraper."""


class Campaign:
    """Cadence par hôte, coupe-circuit par hôte, abandon global."""

    def __init__(self, floor: float, jitter: float, max_blocked: int,
                 max_req: int, verbose: bool):
        self.floor = floor
        self.jitter = jitter
        self.max_blocked = max_blocked
        self.max_req = max_req
        self.verbose = verbose
        self.last_hit: Dict[str, float] = {}
        self.blocked: Dict[str, str] = {}
        self.lock = threading.Lock()
        self.log: List[dict] = []
        self.current: Optional[List[Any]] = None
        self.unreachable: Dict[str, str] = {}
        self.refused: set = set()
        self.http_responses = 0

    # -- cadence -----------------------------------------------------------
    def wait_for(self, host: str, scraper_rate: float) -> float:
        """Attend le max entre la cadence du scraper et celle de la campagne."""
        key = rate_key(host)
        delay = max(float(scraper_rate or 1.0), self.floor)
        with self.lock:
            last = self.last_hit.get(key, 0.0)
            slept = 0.0
            gap = time.time() - last
            if last and gap < delay:
                slept = delay - gap
            if self.jitter:
                slept += random.uniform(0.0, self.jitter)
        if slept > 0:
            time.sleep(slept)
        with self.lock:
            self.last_hit[key] = time.time()
        return slept

    # -- garde-fous --------------------------------------------------------
    def before(self, url: str) -> str:
        host = (urlsplit(url).hostname or "?").lower()
        key = rate_key(host)
        if key in self.blocked:
            raise HostRefused(f"{key} a répondu {self.blocked[key]} — pas de relance")
        if self.current and self.current[1] >= self.max_req:
            raise BudgetExhausted(
                f"{self.current[0]} : plafond de {self.max_req} requêtes atteint"
            )
        return host

    def block(self, host: str, why: str, counts_as_refusal: bool = True) -> None:
        key = rate_key(host)
        if key in self.blocked:
            return
        self.blocked[key] = why
        if counts_as_refusal:
            self.refused.add(key)
        kind = "refus" if counts_as_refusal else "quota"
        print(f"      ⛔ {key} (via {host}) → {why} [{kind}] ; domaine retiré "
              f"de la campagne")
        if len(self.refused) >= self.max_blocked:
            raise CampaignAbort(
                f"{len(self.refused)} domaines ont REFUSÉ "
                f"({', '.join(sorted(self.refused))}) — l'adresse de sortie "
                f"est probablement marquée, campagne interrompue"
            )

    def record(self, sid, host, url, status, elapsed, slept, err=None):
        self.log.append({
            "scraper": sid, "host": host, "url": url[:200], "status": status,
            "ms": round(elapsed * 1000), "waited_s": round(slept, 2), "error": err,
        })
        if status is not None:
            self.http_responses += 1
        elif err and is_transport_failure(err):
            self.unreachable.setdefault(rate_key(host), err[:160])
        if self.verbose:
            print(f"      · {status or 'ERR':>4} {host}  "
                  f"(attente {slept:.1f}s, réponse {elapsed:.1f}s)")


#: Méthodes d'origine de `BaseScraper`, mémorisées au premier habillage.
#: Sans cela, un second appel à `install_guard()` envelopperait la version déjà
#: enveloppée : la campagne précédente resterait branchée par la fermeture,
#: continuerait de compter ses hôtes bloqués et déclencherait l'abandon global
#: de la campagne suivante. Une exécution normale n'appelle `main()` qu'une
#: fois, mais les tests du garde-fou, eux, l'appellent en boucle.
_PRISTINE: Dict[str, Any] = {}


def force_impersonate(profile: str) -> None:
    """Impose une empreinte TLS à tous les scrapers `curl_cffi`.

    Uniquement pour valider depuis un réseau qui n'accepte pas l'empreinte
    d'origine. Certains intermédiaires (proxy d'entreprise, bac à sable) ne
    savent pas négocier les empreintes Chrome récentes et coupent la connexion
    avant le site : le scraper est alors intestable pour une raison qui ne lui
    appartient pas. Retomber sur une empreinte plus ancienne rend le test
    possible.

    Les verdicts obtenus ainsi sont INDICATIFS : ils valident la logique du
    scraper (recherche, appariement, forme de la charge utile), pas son
    comportement en production, où l'empreinte déclarée est justement celle qui
    lui permet de passer. Un site peut refuser l'empreinte forcée tout en
    acceptant l'originale, et l'inverse est vrai aussi.
    """
    try:
        from curl_cffi import requests as cr
    except ImportError:
        print("curl_cffi absent : --impersonate sans effet")
        return
    # Deux points d'entrée à couvrir, pas un. Un scraper peut fixer
    # l'empreinte à la construction de la session — et un autre la repasser
    # requête par requête, auquel cas la valeur de la requête l'emporte sur
    # celle de la session. Ne corriger que le constructeur laissait ces
    # derniers échouer exactement comme avant, en donnant l'illusion que
    # l'empreinte n'était pas en cause.
    init = cr.Session.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["impersonate"] = profile
        return init(self, *args, **kwargs)

    cr.Session.__init__ = patched_init

    request = cr.Session.request

    def patched_request(self, *args, **kwargs):
        kwargs["impersonate"] = profile
        return request(self, *args, **kwargs)

    cr.Session.request = patched_request
    print(f"⚠️  empreinte TLS forcée à « {profile} » pour tous les scrapers "
          f"curl_cffi — verdicts INDICATIFS, l'empreinte de production diffère")


def install_guard(campaign: Campaign):
    """Enveloppe l'unique point de sortie HTTP de tous les scrapers.

    Idempotent : on repart toujours des méthodes d'origine, jamais d'un
    habillage déjà posé.
    """
    from scrapers.base import BaseScraper

    def wrap(method_name: str):
        original = _PRISTINE.setdefault(
            method_name, getattr(BaseScraper, method_name)
        )

        def guarded(self, client, url, **kwargs):
            host = campaign.before(url)
            slept = campaign.wait_for(host, getattr(self, "rate_limit", 1.0))
            if campaign.current:
                campaign.current[1] += 1
            kwargs.setdefault("timeout", getattr(self, "http_timeout", 20.0))
            t0 = time.time()
            try:
                res = original(self, client, url, **kwargs)
            except Exception as exc:
                campaign.record(self.id, host, url, None, time.time() - t0,
                                slept, repr(exc)[:200])
                raise
            elapsed = time.time() - t0
            status = getattr(res, "status_code", None)
            campaign.record(self.id, host, url, status, elapsed, slept)

            if status in PUSHBACK:
                retry_after = ""
                try:
                    ra = (res.headers or {}).get("Retry-After")
                    retry_after = f" (Retry-After: {ra})" if ra else ""
                except Exception:
                    pass
                campaign.block(host, f"HTTP {status}{retry_after}",
                               counts_as_refusal=status in REFUSALS)
                raise HostRefused(f"{host} → HTTP {status}")

            if status == 200:
                try:
                    body = (res.text or "")[:4000].casefold()
                except Exception:
                    body = ""
                if any(m in body for m in CF_MARKERS):
                    campaign.block(host, "interstitielle anti-bot (Cloudflare)")
                    raise HostRefused(f"{host} → Cloudflare")
            return res

        guarded.__name__ = method_name
        setattr(BaseScraper, method_name, guarded)

    wrap("_http_get")
    wrap("_http_post")


def retired_files() -> set:
    try:
        cat = json.loads((ROOT / "store" / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    out = set()
    for e in cat.get("scrapers") or []:
        tags = {str(t).lower() for t in e.get("tags") or []}
        states = {str(e.get(k) or "").lower() for k in ("lifecycle", "status")}
        if e.get("retired") is True or "retired" in (tags | states):
            out.add(str(e.get("file") or ""))
    return out - {""}


def load_classes(path: Path) -> List[type]:
    from scrapers.base import BaseScraper

    name = f"live_validation_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"chargement impossible : {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return [
        obj for _, obj in inspect.getmembers(mod, inspect.isclass)
        if obj.__module__ == mod.__name__
        and issubclass(obj, BaseScraper) and obj is not BaseScraper
    ]


def config_value(name: str) -> str:
    try:
        from config_manager import load_config
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    return str(cfg.get(name) or os.environ.get(name) or "").strip()


def validate_candidate(meta: dict) -> List[str]:
    errs = []
    if not isinstance(meta, dict):
        return ["candidat non-dict"]
    for k in sorted(REQUIRED_CAND_KEYS - set(meta)):
        errs.append(f"clé manquante : {k}")
    if not isinstance(meta.get("title"), str) or not meta.get("title"):
        errs.append("title invalide")
    if not isinstance(meta.get("genres"), list):
        errs.append("genres doit être une liste")
    if not isinstance(meta.get("tags"), list):
        errs.append("tags doit être une liste")
    staff = meta.get("staff")
    if not isinstance(staff, list):
        errs.append("staff doit être une liste")
    else:
        for i, s in enumerate(staff[:5]):
            try:
                _ = s["node"]["name"]["full"]
            except Exception:
                errs.append(f"staff[{i}] mal formé")
    if meta.get("format") not in {"manga", "webtoon", "comic", "book", None}:
        errs.append(f"format inattendu : {meta.get('format')!r}")
    score = meta.get("_match_score")
    if score is not None:
        try:
            if not 0.0 <= float(score) <= 1.0:
                errs.append(f"_match_score hors [0,1] : {score}")
        except Exception:
            errs.append(f"_match_score non numérique : {score!r}")
    if meta.get("status") not in {None, "RELEASING", "FINISHED", "HIATUS", "CANCELLED"}:
        errs.append(f"status invalide : {meta.get('status')!r}")
    if meta.get("age_rating") not in {None, "safe", "suggestive", "erotica", "pornographic"}:
        errs.append(f"age_rating invalide : {meta.get('age_rating')!r}")
    if meta.get("year") is not None and not isinstance(meta.get("year"), int):
        errs.append(f"year non-int : {meta.get('year')!r}")
    return errs


def pick_query(inst) -> Tuple[str, str]:
    if inst.id in QUERY_OVERRIDE:
        return QUERY_OVERRIDE[inst.id]
    for t in ("Manga", "Comic", "Book"):
        if t in (inst.supported_types or set()):
            return DEFAULT_QUERY[t]
    return DEFAULT_QUERY["Comic"]


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Validation live du catalogue, avec garde-fous anti-ban.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--only", default="", help="ids séparés par des virgules")
    p.add_argument("--exclude", default="", help="ids à ne pas interroger")
    p.add_argument("--floor", type=float, default=4.0,
                   help="cadence plancher par hôte, en secondes (défaut 4.0). "
                        "La cadence appliquée est max(rate_limit, floor).")
    p.add_argument("--jitter", type=float, default=1.5,
                   help="secondes aléatoires ajoutées à chaque attente (défaut 1.5)")
    p.add_argument("--gap", type=float, default=5.0,
                   help="pause entre deux scrapers, en secondes (défaut 5.0)")
    p.add_argument("--max-req", type=int, default=15,
                   help="plafond de requêtes par scraper (défaut 15)")
    p.add_argument("--max-blocked", type=int, default=3,
                   help="nombre d'hôtes bloqués qui interrompt la campagne (défaut 3)")
    p.add_argument("--max-unreachable", type=int, default=3,
                   help="scrapers injoignables d'affilée, sans aucune réponse HTTP, "
                        "qui interrompent la campagne (défaut 3) — signe que la "
                        "machine n'a pas d'accès sortant, pas que le code est cassé")
    p.add_argument("--dry-run", action="store_true",
                   help="affiche le plan et le trafic estimé, n'émet rien")
    p.add_argument("--resume", action="store_true",
                   help="ne réinterroge pas les scrapers déjà concluants du rapport")
    p.add_argument("--impersonate", default="",
                   help="force l'empreinte TLS curl_cffi (ex. chrome110). "
                        "Uniquement pour tester depuis un réseau qui refuse "
                        "l'empreinte d'origine ; les verdicts deviennent "
                        "indicatifs, pas représentatifs de la production.")
    p.add_argument("--verbose", action="store_true", help="journalise chaque requête")
    p.add_argument("--report", default=str(ROOT / "tests" / "_live_validation.json"))
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    only = {s.strip().upper() for s in args.only.split(",") if s.strip()}
    exclude = {s.strip().upper() for s in args.exclude.split(",") if s.strip()}
    report_path = Path(args.report)

    previous: Dict[str, dict] = {}
    carried: Dict[str, dict] = {}
    carried_requests: List[dict] = []
    resumed_http = 0
    if args.resume and report_path.exists():
        try:
            old = json.loads(report_path.read_text(encoding="utf-8"))
            # Tout est repris, pas seulement ce qu'on saute. Le rapport est à la
            # fois l'entrée et la sortie de `--resume` : n'y réécrire que la
            # passe courante fait disparaître les résultats des passes
            # précédentes dès qu'une reprise s'interrompt tôt. C'est arrivé —
            # une passe avortée a effacé cinq scrapers validés en direct, et la
            # reprise suivante a cru repartir de rien.
            carried = {
                r["id"]: r for r in old.get("results", []) if r.get("id")
            }
            carried_requests = list(old.get("requests") or [])
            # Un NO-MATCH n'est pas concluant : c'est l'absence de résultat,
            # donc exactement ce qu'on relance après avoir corrigé un scraper.
            # Le compter comme acquis figeait dans le rapport le verdict d'un
            # code qui n'existe plus.
            previous = {
                sid: r for sid, r in carried.items()
                if r.get("verdict") in {"OK", "SHAPE"}
            }
            print(f"reprise : {len(carried)} lignes conservées, "
                  f"{len(previous)} scrapers déjà concluants non réinterrogés")
            # Les lignes rejouées n'émettent aucune requête : sans ce report,
            # le compteur de réponses HTTP repart à zéro et le diagnostic
            # « aucun accès sortant » se déclenche sur les premiers scrapers
            # injoignables — alors que le rapport prouve le contraire.
            resumed_http = sum(
                1 for r in carried_requests if r.get("status") is not None
            )
            # Un rapport peut avoir perdu son journal de requêtes ; un verdict
            # OK reste la preuve qu'une réponse HTTP est arrivée.
            resumed_http += sum(
                1 for r in carried.values()
                if r.get("verdict") in {"OK", "SHAPE", "NO-MATCH", "BLOCKED"}
            )
        except Exception as exc:
            print(f"reprise impossible ({exc}) — campagne complète")

    skip = SKIP_FILES | retired_files()
    files = [
        f for f in sorted(ROOT.glob("*.py"))
        if not f.name.startswith("_") and f.name not in skip
    ]

    campaign = Campaign(args.floor, args.jitter, args.max_blocked,
                        args.max_req, args.verbose)
    campaign.http_responses = resumed_http

    print(f"MetaKavita : {MK}")
    print(f"cadence    : max(rate_limit, {args.floor}s) par DOMAINE, +0–{args.jitter}s "
          f"d'aléa, {args.gap}s entre scrapers")
    print(f"garde-fous : {args.max_req} requêtes/scraper max, campagne "
          f"interrompue à {args.max_blocked} domaines en REFUS "
          f"(un 429 de quota ne compte pas), aucun réessai")
    print(f"retirés    : {sorted(skip - SKIP_FILES) or 'aucun'}\n")

    plan = []
    for path in files:
        try:
            classes = load_classes(path)
        except Exception as exc:
            print(f"[IMPORT] {path.name} : {exc}")
            continue
        for cls in classes:
            inst = cls()
            if only and inst.id not in only:
                continue
            if inst.id in exclude:
                continue
            plan.append((path, inst))

    if args.dry_run:
        print(f"=== PLAN ({len(plan)} scrapers) ===")
        worst = 0.0
        for _path, inst in plan:
            rate = max(float(getattr(inst, "rate_limit", 1.0) or 1.0), args.floor)
            q, lib = pick_query(inst)
            est = rate * 3 + args.gap
            worst += rate * args.max_req + args.gap
            print(f"  {inst.id:16} {rate:>5.1f}s/req  '{q}' ({lib})")
        print(f"\nplafond théorique : {worst/60:.0f} min si chaque scraper "
              f"saturait ses {args.max_req} requêtes (jamais observé : "
              f"5 requêtes suffisent au pire mesuré)")
        print("aucune requête émise (--dry-run)")
        return 0

    if args.impersonate:
        force_impersonate(args.impersonate)
    install_guard(campaign)

    results: List[dict] = []
    aborted = None
    unreachable_streak = 0

    def flush():
        # Fusion : les lignes de cette passe écrasent les homonymes, le reste
        # est conservé. Le rapport ne peut donc que s'enrichir.
        merged = dict(carried)
        for row in results:
            if row.get("id"):
                merged[row["id"]] = row
        report_path.write_text(json.dumps({
            "policy": {
                "floor": args.floor, "jitter": args.jitter, "gap": args.gap,
                "max_req": args.max_req, "max_blocked": args.max_blocked,
                "forced_impersonate": args.impersonate or None,
            },
            "blocked_hosts": campaign.blocked,
            "aborted": aborted,
            "results": sorted(merged.values(), key=lambda r: r.get("id") or ""),
            "requests": carried_requests + campaign.log,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    for path, inst in plan:
        if inst.id in previous:
            results.append(previous[inst.id])
            print(f"[REPRISE] {inst.id:15} déjà validé, non réinterrogé")
            continue

        row: Dict[str, Any] = {
            "file": path.name, "id": inst.id,
            "declared_rate": getattr(inst, "rate_limit", None),
            "verdict": "?", "detail": "", "requests": 0,
        }

        env = KEY_ENV.get(inst.id)
        if env and not config_value(env) and inst.id not in OPTIONAL_KEYS:
            if getattr(inst, "needs_api_key", False):
                row.update(verdict="SKIP", detail=f"clé absente ({env})")
                print(f"[SKIP]    {inst.id:15} clé absente ({env})")
                results.append(row)
                flush()
                continue

        q, lib = pick_query(inst)
        row["query"] = q
        campaign.current = [inst.id, 0]
        t0 = time.time()
        meta = None
        failure = None
        try:
            meta = inst.fetch(
                q, library_type=lib, is_id=False,
                existing_metadata={"year": 1986} if inst.id == "GCD" else None,
            )
        except CampaignAbort as exc:
            aborted = str(exc)
            row.update(verdict="ABORTED", detail=str(exc))
            row["requests"] = campaign.current[1]
            results.append(row)
            flush()
            print(f"\n🛑 {exc}")
            break
        except HostRefused as exc:
            failure = f"BLOCKED: {exc}"
        except BudgetExhausted as exc:
            failure = f"BUDGET: {exc}"
        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"
            if args.verbose:
                traceback.print_exc()

        row["requests"] = campaign.current[1]
        row["wall_s"] = round(time.time() - t0, 1)
        hosts = sorted({r["host"] for r in campaign.log if r["scraper"] == inst.id})
        row["hosts"] = hosts

        # Toutes les requêtes de ce scraper ont échoué avant d'obtenir une
        # réponse HTTP : c'est l'environnement, pas le scraper.
        own = [r for r in campaign.log if r["scraper"] == inst.id]
        never_answered = bool(own) and all(
            r["status"] is None and is_transport_failure(r.get("error") or "")
            for r in own
        )

        if never_answered:
            reason = (own[-1].get("error") or "").strip()
            row.update(verdict="UNREACHABLE", detail=f"aucune réponse HTTP — {reason[:200]}")
            print(f"[UNREACH] {inst.id:15} {hosts} injoignable — {reason[:90]}")
            unreachable_streak += 1
            results.append(row)
            flush()
            # Rien n'est jamais parvenu à quoi que ce soit : inutile de
            # dérouler le reste du catalogue pour réécrire la même ligne
            # quarante fois. Ce n'est pas un verdict sur les scrapers.
            if unreachable_streak >= args.max_unreachable and campaign.http_responses == 0:
                tls_only = all(
                    "ssl" in (r.get("error") or "").casefold()
                    or "certificate" in (r.get("error") or "").casefold()
                    for r in campaign.log if r.get("status") is None
                )
                aborted = (
                    f"{unreachable_streak} scrapers d'affilée injoignables et pas "
                    f"une seule réponse HTTP depuis le début : cette machine n'a "
                    f"pas d'accès sortant vers les sites du catalogue. Aucun "
                    f"verdict sur les scrapers n'est possible ici."
                )
                if tls_only:
                    # Un échec de poignée de main n'est pas une absence de
                    # réseau : c'est souvent l'empreinte TLS du client que
                    # l'intermédiaire refuse. Le dire évite de conclure trop
                    # vite que la machine est coupée du monde.
                    aborted += (
                        " Toutes les erreurs sont des échecs TLS : c'est plus "
                        "probablement l'empreinte `impersonate` du client que "
                        "refuse un intermédiaire qu'une absence de réseau. "
                        "Essayez une empreinte plus ancienne (chrome110)."
                    )
                print(f"\n🛑 {aborted}")
                break
            time.sleep(args.gap)
            continue
        unreachable_streak = 0

        if failure and failure.startswith("BLOCKED"):
            row.update(verdict="BLOCKED", detail=failure)
            print(f"[BLOCKED] {inst.id:15} {failure}")
        elif failure:
            row.update(verdict="ERROR", detail=failure[:300])
            print(f"[ERROR]   {inst.id:15} '{q}' → {failure[:110]}")
        elif meta is None and any(rate_key(h) in campaign.blocked for h in hosts):
            # Ceinture et bretelles : si un scraper avalait malgré tout le
            # signal d'arrêt, l'hôte bloqué reste la vraie cause du None.
            refused = sorted({rate_key(h) for h in hosts} & set(campaign.blocked))
            row.update(
                verdict="BLOCKED",
                detail="domaine refusé : "
                       + ", ".join(f"{k} ({campaign.blocked[k]})" for k in refused),
            )
            print(f"[BLOCKED] {inst.id:15} {row['detail']}")
        elif meta is None:
            optional_key_missing = inst.id in OPTIONAL_KEYS and env and not config_value(env)
            row.update(
                verdict="EXPECTED" if optional_key_missing else "NO-MATCH",
                detail=("aucun résultat, clé/cookies facultatifs absents"
                        if optional_key_missing else f"fetch() a rendu None pour '{q}'"),
            )
            print(f"[{row['verdict']:8}] {inst.id:15} '{q}' → None "
                  f"({row['requests']} req, {row['wall_s']}s)")
        else:
            errs = validate_candidate(meta)
            row.update(
                title=meta.get("title"), score=meta.get("_match_score"),
                cover=bool(meta.get("cover_url")), year=meta.get("year"),
                shape_errors=errs,
                verdict="SHAPE" if errs else "OK",
                detail=(f"'{meta.get('title')}' score={meta.get('_match_score')} "
                        f"cover={'oui' if meta.get('cover_url') else 'non'} "
                        f"year={meta.get('year')}"
                        + (f" | forme : {'; '.join(errs)}" if errs else "")),
            )
            tag = "OK" if not errs else "SHAPE"
            print(f"[{tag:8}] {inst.id:15} {row['detail']} "
                  f"({row['requests']} req, {row['wall_s']}s)")

        results.append(row)
        flush()
        time.sleep(args.gap)

    flush()

    print("\n=== RÉSUMÉ ===")
    from collections import Counter
    counts = Counter(r["verdict"] for r in results)
    for verdict in ("OK", "SHAPE", "NO-MATCH", "EXPECTED", "BLOCKED",
                    "UNREACHABLE", "ERROR", "SKIP", "ABORTED"):
        if counts.get(verdict):
            print(f"  {verdict:10} {counts[verdict]}")
    print(f"  requêtes émises : {len(campaign.log)}")
    print(f"  domaines bloqués: {campaign.blocked or 'aucun'}")
    quota_only = sorted(set(campaign.blocked) - campaign.refused)
    if quota_only:
        print(f"    dont quota seulement (n'accuse pas l'IP) : {quota_only}")
    if campaign.unreachable:
        print(f"  domaines injoignables (transport) : {len(campaign.unreachable)}")
        for dom, why in list(campaign.unreachable.items())[:5]:
            print(f"    {dom:22} {why[:80]}")
    print(f"  réponses HTTP reçues : {campaign.http_responses}")
    if aborted:
        print(f"\n🛑 campagne interrompue : {aborted}")
        if campaign.http_responses == 0 and campaign.unreachable:
            # Attendre ne répare pas une machine sans accès sortant : le
            # conseil « réessayez plus tard » n'a de sens que pour un refus.
            print("   Rien n'a atteint le réseau : ce n'est pas une question de "
                  "cadence et attendre n'y changera rien.")
            print("   Relancez depuis une machine ayant un accès sortant vers "
                  "ces domaines (proxy de sortie, pare-feu, conteneur isolé).")
        else:
            print("   Attendez plusieurs heures avant de relancer, puis "
                  "`--resume` pour ne reprendre que ce qui manque.")
    print(f"  rapport → {report_path}")

    # Seuls ERROR / NO-MATCH / SHAPE sont des échecs du code. BLOCKED,
    # UNREACHABLE et ABORTED décrivent l'environnement réseau, pas le scraper :
    # les compter comme des échecs ferait chercher des bugs inexistants.
    failures = sum(counts.get(v, 0) for v in ("ERROR", "NO-MATCH", "SHAPE"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
