"""BnF Catalogue — métadonnées livres via SRU Dublin Core (gratuit, sans clé)."""
from __future__ import annotations

import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_SRU = "https://catalogue.bnf.fr/api/SRU"
_PORTAL = "https://catalogue.bnf.fr"
_NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_NON_ISBN = re.compile(r"[^0-9Xx]")
_ARK = re.compile(r"(ark:/12148/[a-z0-9]+)", re.I)


def _norm_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = _NON_ISBN.sub("", str(raw)).upper()
    return c if len(c) in (10, 13) else None


def _cql_quote(term: str) -> str:
    return '"' + term.replace("\\", "\\\\").replace('"', '\\"') + '"'


# --- Cadence des requêtes (repli de compatibilité) ---------------------------
# `BaseScraper._http_get` applique le `rate_limit` du scraper AVANT CHAQUE
# requête. Sans lui, la cadence n'est honorée qu'une fois par `fetch()`, par
# l'appelant, et les requêtes émises À L'INTÉRIEUR partent en rafale : c'est ce
# profil de trafic qui fait bannir une IP sur un site sans API. Ce helper est
# récent, et un scraper du catalogue peut être installé sur une image MetaKavita
# antérieure où l'appeler lèverait `AttributeError` à l'exécution. On sonde donc
# sa présence à chaque appel et, quand il manque, on refait son travail ici :
# aucun chemin ne doit pouvoir émettre une requête non cadencée.
_LAST_CALL: dict = {}
_LAST_CALL_LOCK = threading.Lock()


def _throttle_fallback(scraper) -> None:
    """Attend le solde du `rate_limit` sur les images sans `_http_get`.

    `services.provider_throttle` est privilégié quand il existe : c'est
    l'horloge que partagent tous les chemins de l'application (enrichissement,
    recherche de couvertures, diagnostic), et tenir un compteur séparé
    reviendrait à autoriser deux fois la cadence sur le même fournisseur. Le
    compteur local ci-dessous n'est qu'un dernier recours, pour une image qui
    n'aurait même pas ce module.
    """
    try:
        from services.provider_throttle import throttle_provider
    except Exception:
        pass
    else:
        throttle_provider(scraper)
        return

    delay = float(getattr(scraper, "rate_limit", 1.0) or 0.0)
    key = getattr(scraper, "id", "") or scraper.__class__.__name__
    with _LAST_CALL_LOCK:
        last = _LAST_CALL.get(key)
        now = time.monotonic()
        if last is not None and now - last < delay:
            time.sleep(delay - (now - last))
        _LAST_CALL[key] = time.monotonic()


def _throttled_get(scraper, client, url: str, **kwargs):
    """GET cadencé : `BaseScraper._http_get` s'il existe, repli explicite sinon."""
    helper = getattr(scraper, "_http_get", None)
    if callable(helper):
        return helper(client, url, **kwargs)
    _throttle_fallback(scraper)
    kwargs.setdefault("timeout", getattr(scraper, "http_timeout", 20.0))
    return client.get(url, **kwargs)


class BnfScraper(BaseScraper):
    id = "BNF"
    display_name = "BnF Catalogue"
    supported_types = {"Book"}
    # 1.1.0 : `_sru` est appelé plusieurs fois par `fetch()` (ISBN puis titre) et
    # ne payait la cadence qu'une fois. Toutes les requêtes y passent désormais.
    version = "1.1.0"
    rate_limit = 1.0
    proxy_domains = ["bnf.fr", "catalogue.bnf.fr"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [BnF] Recherche pour '{0}'…",
            "search_isbn": "🔎 [BnF] ISBN {0}…",
            "direct_id": "🎯 [BnF] ARK/ID={0}",
            "no_match": "⚠️ [BnF] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [BnF] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [BnF] Erreur : {0}",
            "covers_err": "❌ [Covers] BnF : pas d'images natives SRU",
        },
        "en": {
            "search_title": "🔍 [BnF] Searching for '{0}'…",
            "search_isbn": "🔎 [BnF] ISBN {0}…",
            "direct_id": "🎯 [BnF] ARK/ID={0}",
            "no_match": "⚠️ [BnF] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [BnF] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [BnF] Error: {0}",
            "covers_err": "❌ [Covers] BnF: no native SRU covers",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        m = _ARK.search(url)
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        try:
            if is_id:
                ark = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(ark))
                records = self._sru(session, f"bib.persistentid any {_cql_quote(ark)}", 3)
                for rec in records:
                    cand = self._dc_to_candidate(rec)
                    if cand:
                        return attach_match_score(cand, 1.0)
                return None

            existing_isbn = _norm_isbn(
                (existing_metadata or {}).get("isbn") if existing_metadata else None
            )
            cleaned = clean_title(query, library_type=library_type)
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                records = self._sru(
                    session, f"bib.isbn all {_cql_quote(existing_isbn)}", 5
                )
                for rec in records:
                    cand = self._dc_to_candidate(rec)
                    if not cand:
                        continue
                    if _norm_isbn(cand.get("isbn")) == existing_isbn:
                        return attach_match_score(cand, 1.0)

            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            cql = f"bib.title all {_cql_quote(cleaned)}"
            authors = (existing_metadata or {}).get("authors") or []
            if authors and isinstance(authors[0], str) and authors[0].strip():
                last = authors[0].strip().split()[-1]
                cql = f"{cql} and bib.author all {_cql_quote(last)}"
            records = self._sru(session, cql, 10)
            if not records and " and bib.author " in cql:
                records = self._sru(
                    session, f"bib.title all {_cql_quote(cleaned)}", 10
                )
            best, best_score = None, -1.0
            for rec in records:
                cand = self._dc_to_candidate(rec)
                if not cand or not cand.get("title"):
                    continue
                score = score_candidate(cand, cleaned, existing_metadata)
                if score > best_score:
                    best_score, best = score, cand
            if not best or best_score < get_match_accept_threshold():
                logging.warning(
                    self.t("no_match").format(cleaned, int(max(best_score, 0) * 100))
                )
                return None
            logging.info(self.t("matched").format(best.get("title"), int(best_score * 100)))
            return attach_match_score(best, best_score)
        except Exception as e:
            logging.error(self.t("err").format(e))
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    def fetch_covers(self, query: str, library_type: str = "Book") -> List[Dict[str, str]]:
        return []

    def _sru(self, session, cql: str, maximum: int) -> List[ET.Element]:
        res = _throttled_get(
            self,
            session,
            _SRU,
            params={
                "version": "1.2",
                "operation": "searchRetrieve",
                "query": cql,
                "maximumRecords": str(max(1, min(maximum, 20))),
                "recordSchema": "dublincore",
            },
            timeout=25,
            headers={"Accept": "application/xml"},
        )
        if res.status_code != 200:
            return []
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            return []
        out = []
        for rd in root.findall(".//srw:recordData", _NS):
            dc = rd.find("oai_dc:dc", _NS)
            if dc is not None:
                out.append(dc)
        return out

    def _dc_to_candidate(self, dc: ET.Element) -> Optional[Dict[str, Any]]:
        def texts(tag: str) -> List[str]:
            return [
                (el.text or "").strip()
                for el in dc.findall(f"dc:{tag}", _NS)
                if (el.text or "").strip()
            ]

        titles = texts("title")
        if not titles:
            return None
        title = titles[0].split(" / ", 1)[0].strip()
        title = title.strip("[]").strip()
        # BnF : souvent "[Madame Bovary]" ou "Madame Bovary [Texte imprimé]"
        title = re.sub(r"\s*\[(?:Texte imprimé|Document électronique)\]\s*$", "", title, flags=re.I).strip()
        title = title.strip("[]").strip()
        creators = texts("creator")
        # "Nom, Prénom (dates). Rôle" → Nom Prénom approx
        authors = []
        for c in creators:
            name = c.split(".", 1)[0]
            name = re.sub(r"\s*\([^)]*\)\s*", " ", name).strip()
            if "," in name:
                last, first = name.split(",", 1)
                name = f"{first.strip()} {last.strip()}".strip()
            if name:
                authors.append(name)
        staff = [
            {"role": "Story", "node": {"name": {"full": n}}} for n in authors[:5]
        ]
        year = None
        for d in texts("date"):
            m = _YEAR.search(d)
            if m:
                year = int(m.group(1))
                break
        isbn = None
        for ident in texts("identifier"):
            n = _norm_isbn(ident)
            if n:
                isbn = n
                break
        subjects = texts("subject")
        publishers = texts("publisher")
        descriptions = texts("description")
        ark = None
        for ident in texts("identifier"):
            m = _ARK.search(ident)
            if m:
                ark = m.group(1)
                break
        url = f"{_PORTAL}/{ark}" if ark else None
        return {
            "title": title,
            "alternative_titles": titles[1:4],
            "summary": "\n\n".join(descriptions),
            "cover_url": None,
            "genres": subjects[: get_max_genres()] if subjects else ["Book"],
            "tags": subjects[get_max_genres() : get_max_genres() + get_max_tags()],
            "year": year,
            "staff": staff,
            "publisher": publishers[0] if publishers else None,
            "format": "book",
            "url": url,
            "links": [url] if url else [],
            "isbn": isbn,
        }
