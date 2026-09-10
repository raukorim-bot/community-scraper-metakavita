"""Les garde-fous anti-ban de `run_live_validation.py` sont eux-mêmes testés.

Ce runner n'existe que pour éviter un bannissement d'IP : un garde-fou qui ne
se déclenche pas y est pire qu'absent, parce qu'on lance la campagne en le
croyant actif. Les quatre mécanismes sont donc vérifiés ici, sans réseau — le
transport est remplacé avant que le runner ne pose son habillage.

Deux de ces tests correspondent à des défauts réels trouvés à l'écriture :
le coupe-circuit était avalé par le `except Exception` des scrapers, et la
cadence était indexée sur le nom d'hôte au lieu du domaine.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytest.importorskip(
    "scrapers.base",
    reason="MetaKavita absent du PYTHONPATH (METAKAVITA_ROOT)",
)


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_live_validation", ROOT / "tests" / "run_live_validation.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["run_live_validation"] = mod
    spec.loader.exec_module(mod)
    return mod


class _Resp:
    def __init__(self, status, text):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.headers = {"Retry-After": "120"} if status == 429 else {}
        self.encoding = "utf-8"
        self.url = "https://stub.invalid/"
        self.ok = status == 200

    def json(self):
        try:
            return json.loads(self.text)
        except ValueError:
            return {}


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    """Rend un lanceur de campagne dont le transport est bouchonné."""
    import scrapers.base as base

    runner = _load_runner()
    hits: list = []

    def make(mode):
        def fake(self, client, url, **kwargs):
            hits.append((self.id, url))
            if mode == "boom":
                raise ConnectionError(
                    "Failed to perform, curl: (7) CONNECT tunnel failed, "
                    "response 403"
                )
            if mode == "403":
                return _Resp(403, "Forbidden")
            if mode == "429":
                return _Resp(429, "Too Many Requests")
            if mode == "cf":
                return _Resp(200, "<html><body>Just a moment...</body></html>")
            return _Resp(200, '{"data": [], "results": []}')

        monkeypatch.setattr(base.BaseScraper, "_http_get", fake)
        monkeypatch.setattr(base.BaseScraper, "_http_post", fake)
        # L'habillage doit repartir des méthodes bouchonnées, pas d'un
        # habillage laissé par un test précédent.
        runner._PRISTINE.clear()

        def run(*args):
            report = tmp_path / "report.json"
            runner.main([*args, "--report", str(report)])
            return json.loads(report.read_text(encoding="utf-8"))

        return run, hits

    return make


FAST = ("--floor", "0.1", "--jitter", "0", "--gap", "0.1")


def test_a_refused_domain_is_never_queried_again(campaign):
    """Un 403 retire le domaine ; insister est ce qui transforme un refus en ban."""
    run, _ = campaign("403")
    data = run("--only", "MANGADEX,ANILIST", *FAST, "--max-blocked", "9")

    assert data["blocked_hosts"], "aucun domaine bloqué sur un 403"
    per_domain: dict = {}
    for req in data["requests"]:
        key = req["host"]
        per_domain[key] = per_domain.get(key, 0) + 1
    assert all(n == 1 for n in per_domain.values()), (
        f"un domaine refusé a été réinterrogé : {per_domain}"
    )
    assert {r["verdict"] for r in data["results"]} == {"BLOCKED"}


def test_the_block_survives_the_scrapers_own_except_exception(campaign):
    """Le signal d'arrêt doit traverser le `except Exception` des scrapers.

    Défaut réel : dérivé de `RuntimeError`, il était avalé par le scraper, qui
    passait tranquillement à la requête suivante vers l'hôte refusant.
    """
    runner = _load_runner()
    for exc in (runner.CampaignAbort, runner.HostRefused, runner.BudgetExhausted):
        assert not issubclass(exc, Exception), (
            f"{exc.__name__} dérive de Exception : les scrapers l'avaleront"
        )
        assert issubclass(exc, BaseException)

    run, _ = campaign("403")
    data = run("--only", "MANGADEX", *FAST, "--max-blocked", "9")
    assert [r["verdict"] for r in data["results"]] == ["BLOCKED"], (
        "le refus a été avalé et rapporté comme une simple absence de résultat"
    )


def test_the_campaign_aborts_once_several_domains_refuse(campaign):
    """Plusieurs refus d'affilée = adresse de sortie marquée, pas sites en panne."""
    run, _ = campaign("403")
    data = run("--only", "MANGADEX,ANILIST,KITSU,SHIKIMORI,MANGAUPDATES",
               *FAST, "--max-blocked", "3")

    assert data["aborted"], "la campagne aurait dû s'interrompre"
    assert len(data["blocked_hosts"]) == 3
    # Les scrapers au-delà du seuil ne sont jamais interrogés.
    assert len(data["requests"]) == 3


def test_an_anti_bot_interstitial_is_a_refusal_not_a_success(campaign):
    """Cloudflare répond 200 avec « Just a moment » : ce n'est pas un succès."""
    run, _ = campaign("cf")
    data = run("--only", "BABELIO", *FAST, "--max-blocked", "9")
    assert any("Cloudflare" in why for why in data["blocked_hosts"].values()), (
        f"interstitielle non détectée : {data['blocked_hosts']}"
    )


def test_retry_after_is_captured(campaign):
    run, _ = campaign("429")
    data = run("--only", "MANGADEX", *FAST, "--max-blocked", "9")
    assert any("Retry-After: 120" in why for why in data["blocked_hosts"].values())


def test_cadence_is_keyed_on_the_domain_not_the_hostname(campaign):
    """`www.loc.gov` et `lx2.loc.gov` sont un seul serveur, donc une horloge.

    Défaut réel : indexée sur le nom d'hôte, la cadence laissait LOC émettre
    deux requêtes simultanées vers deux sous-domaines de la même institution.
    """
    runner = _load_runner()
    assert runner.rate_key("lx2.loc.gov") == runner.rate_key("www.loc.gov") == "loc.gov"
    assert runner.rate_key("ndlsearch.ndl.go.jp") == "ndl.go.jp"  # suffixe composé
    assert runner.rate_key("api.mangadex.org") == "mangadex.org"

    run, hits = campaign("ok")
    hits.clear()
    data = run("--only", "LOC", "--floor", "2.0", "--jitter", "0", "--gap", "0")

    domains = {runner.rate_key(urlsplit(r["url"]).hostname or "") for r in data["requests"]}
    assert domains == {"loc.gov"}, domains
    waits = [r["waited_s"] for r in data["requests"]]
    if len(waits) > 1:
        assert all(w >= 1.9 for w in waits[1:]), (
            f"cadence non respectée à l'intérieur du domaine : {waits}"
        )


def test_a_transport_failure_is_not_reported_as_a_broken_scraper(campaign):
    """Ne jamais atteindre le site n'est pas un verdict sur le scraper.

    Sur une machine sans accès sortant, chaque `fetch()` lève une erreur de
    connexion. Rapporté en ERROR, cela ressemble à quarante scrapers cassés et
    envoie déboguer du code parfaitement sain.
    """
    runner = _load_runner()
    assert runner.is_transport_failure(
        "ProxyError('Unable to connect to proxy', "
        "OSError('Tunnel connection failed: 403 Forbidden'))"
    )
    assert runner.is_transport_failure("curl: (7) CONNECT tunnel failed, response 403")
    # Un refus applicatif ne doit pas être confondu avec une panne de transport.
    assert not runner.is_transport_failure("HTTP 403 Forbidden")
    assert not runner.is_transport_failure("no match for query")

    run, _ = campaign("boom")
    data = run("--only", "MANGADEX", *FAST, "--max-unreachable", "9")
    assert [r["verdict"] for r in data["results"]] == ["UNREACHABLE"]


def test_no_egress_at_all_stops_the_run_instead_of_repeating_itself(campaign):
    """Zéro réponse HTTP = environnement, pas catalogue : on s'arrête tout de suite."""
    run, _ = campaign("boom")
    data = run("--only", "MANGADEX,ANILIST,KITSU,SHIKIMORI,MANGAUPDATES",
               *FAST, "--max-unreachable", "3")

    assert data["aborted"], "la campagne aurait dû s'arrêter"
    assert "pas d'accès sortant" in data["aborted"]
    assert len(data["results"]) == 3, "les scrapers suivants ne sont pas interrogés"


def test_unreachable_is_not_counted_as_a_failure(campaign):
    """Le code de sortie ne doit pas accuser les scrapers d'un problème réseau."""
    runner = _load_runner()
    import scrapers.base as base
    run, _ = campaign("boom")
    data = run("--only", "MANGADEX", *FAST, "--max-unreachable", "9")
    assert all(r["verdict"] == "UNREACHABLE" for r in data["results"])
    # main() rend 0 : aucun ERROR / NO-MATCH / SHAPE.
    assert not [r for r in data["results"]
                if r["verdict"] in {"ERROR", "NO-MATCH", "SHAPE"}]


def test_a_quota_429_blocks_the_domain_without_accusing_the_exit_address(campaign):
    """Un 429 vide un compteur ; il ne dit pas que l'IP est grillée.

    Trouvé en campagne réelle : anilist.co 403, bdtheque.com 403 et
    googleapis.com 429 (quota anonyme partagé) ont été additionnés pour
    conclure « adresse marquée », ce qui a interrompu une campagne qui se
    déroulait normalement. Le 429 retire bien le domaine — insister sur une
    API qui compte les appels est exactement ce qu'il ne faut pas faire —
    mais il ne compte plus dans le seuil d'abandon.
    """
    runner = _load_runner()
    assert 429 in runner.PUSHBACK, "un 429 doit retirer le domaine"
    assert 429 not in runner.REFUSALS, "un 429 ne doit pas accuser l'adresse"
    assert {401, 403, 503} <= runner.REFUSALS

    run, _ = campaign("429")
    data = run("--only", "MANGADEX,ANILIST,KITSU,SHIKIMORI,MANGAUPDATES",
               *FAST, "--max-blocked", "3")

    # Cinq domaines en quota : tous retirés, aucune interruption.
    assert not data["aborted"], (
        f"un quota plein ne doit pas interrompre la campagne : {data['aborted']}"
    )
    assert len(data["blocked_hosts"]) == 5
    assert {r["verdict"] for r in data["results"]} == {"BLOCKED"}


def test_resume_keeps_the_evidence_that_the_network_works(campaign, tmp_path):
    """Une reprise ne doit pas rediagnostiquer « machine sans réseau ».

    Trouvé en campagne réelle : les lignes rejouées depuis le rapport
    n'émettent aucune requête, donc le compteur de réponses HTTP repartait à
    zéro. Les trois premiers scrapers réellement interrogés étant injoignables
    (une empreinte TLS refusée par un intermédiaire), la reprise concluait
    « aucun accès sortant » juste après une passe qui avait validé cinq
    scrapers.
    """
    runner = _load_runner()
    report = tmp_path / "report.json"

    # Un rapport de passe précédente : un scraper concluant, des requêtes
    # ayant bel et bien reçu des réponses HTTP.
    report.write_text(json.dumps({
        "policy": {}, "blocked_hosts": {}, "aborted": None,
        "results": [{"id": "BEDETHEQUE", "file": "bedetheque.py",
                     "verdict": "OK", "detail": "ok"}],
        "requests": [{"scraper": "BEDETHEQUE", "host": "www.bedetheque.com",
                      "url": "https://www.bedetheque.com/", "status": 200,
                      "ms": 100, "waited_s": 0, "error": None}],
    }), encoding="utf-8")

    run, _ = campaign("boom")
    runner.main(["--resume", "--only", "BEDETHEQUE,MANGADEX,ANILIST,KITSU",
                 *FAST, "--max-unreachable", "3", "--report", str(report)])
    data = json.loads(report.read_text(encoding="utf-8"))

    assert not data["aborted"], (
        "la reprise a conclu à une absence de réseau malgré un rapport qui "
        f"prouve le contraire : {data['aborted']}"
    )


def test_an_aborted_resume_does_not_erase_the_previous_pass(campaign, tmp_path):
    """Le rapport est entrée ET sortie de `--resume` : il ne doit qu'enrichir.

    Trouvé en campagne réelle : une reprise interrompue au bout de trois
    scrapers a réécrit le rapport avec ses seules lignes, effaçant cinq
    scrapers validés en direct à la passe précédente. La reprise suivante a
    donc cru repartir de presque rien — et le point de reprise, dont le rôle
    est justement de ne pas repayer le trafic, l'avait fait perdre.
    """
    runner = _load_runner()
    report = tmp_path / "report.json"
    report.write_text(json.dumps({
        "policy": {}, "blocked_hosts": {}, "aborted": None,
        "results": [
            {"id": "BEDETHEQUE", "verdict": "OK", "detail": "ok"},
            {"id": "DECITRE", "verdict": "OK", "detail": "ok"},
            {"id": "BNF", "verdict": "OK", "detail": "ok"},
        ],
        "requests": [{"scraper": "BEDETHEQUE", "host": "www.bedetheque.com",
                      "url": "https://x/", "status": 200, "ms": 1,
                      "waited_s": 0, "error": None}],
    }), encoding="utf-8")

    run, _ = campaign("boom")
    runner.main(["--resume", "--only", "MANGADEX,ANILIST,KITSU,SHIKIMORI",
                 *FAST, "--max-unreachable", "2", "--report", str(report)])
    data = json.loads(report.read_text(encoding="utf-8"))

    kept = {r["id"] for r in data["results"]}
    assert {"BEDETHEQUE", "DECITRE", "BNF"} <= kept, (
        f"une passe interrompue a effacé des résultats antérieurs : {kept}"
    )
