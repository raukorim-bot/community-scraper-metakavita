"""BNE (Biblioteca Nacional de España) — livres ES via SRU Alma (gratuit, sans clé)."""
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

_SRU = "https://catalogo.bne.es/view/sru/34BNE_INST"
_PORTAL = "https://catalogo.bne.es"
_NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "marc": "http://www.loc.gov/MARC21/slim",
}
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_NON_ISBN = re.compile(r"[^0-9Xx]")


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


class BneScraper(BaseScraper):
    id = "BNE"
    display_name = "BNE (España)"
    supported_types = {"Book"}
    # 1.1.0 : `_sru` est appelé plusieurs fois par `fetch()` (ISBN puis titre) et
    # ne payait la cadence qu'une fois. Toutes les requêtes y passent désormais.
    version = "1.1.0"
    rate_limit = 1.2
    proxy_domains = ["bne.es", "catalogo.bne.es", "datos.bne.es", "www.bne.es"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [BNE] Recherche pour '{0}'…",
            "search_isbn": "🔎 [BNE] ISBN {0}…",
            "direct_id": "🎯 [BNE] id={0}",
            "no_match": "⚠️ [BNE] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [BNE] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [BNE] Erreur : {0}",
            "covers_err": "❌ [Covers] BNE : pas d'images natives SRU",
        },
        "en": {
            "search_title": "🔍 [BNE] Searching for '{0}'…",
            "search_isbn": "🔎 [BNE] ISBN {0}…",
            "direct_id": "🎯 [BNE] id={0}",
            "no_match": "⚠️ [BNE] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [BNE] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [BNE] Error: {0}",
            "covers_err": "❌ [Covers] BNE: no native SRU covers",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = url.strip()
        if raw.isdigit():
            return raw
        m = re.search(r"(?:mms_id|record[=/]|alma[./])[=/]?(\d{8,})", raw, re.I)
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            if is_id:
                rid = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(rid))
                records = self._sru(f"alma.source_record_id={_cql_quote(rid)}", 3)
                if not records:
                    records = self._sru(f"alma.all_for_ui={_cql_quote(rid)}", 3)
                for rec in records:
                    cand = self._dc_to_candidate(rec)
                    if cand:
                        return attach_match_score(cand, 1.0)
                return None

            existing_isbn = _norm_isbn((existing_metadata or {}).get("isbn"))
            cleaned = clean_title(query, library_type=library_type)
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                records = self._sru(f"alma.isbn={_cql_quote(existing_isbn)}", 5)
                for rec in records:
                    cand = self._dc_to_candidate(rec)
                    if cand and _norm_isbn(cand.get("isbn")) == existing_isbn:
                        return attach_match_score(cand, 1.0)

            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            # Alma : guillemets = phrase exacte (trop strict) → essayer aussi sans
            queries = [
                f"alma.title={_cql_quote(cleaned)}",
                f"alma.title={cleaned}",
                f"alma.all_for_ui={_cql_quote(cleaned)}",
            ]
            # Terme discriminant (ex. Quijote)
            tokens = [t for t in cleaned.replace("¡", "").replace("¿", "").split() if len(t) > 3]
            if tokens:
                queries.append(f"alma.title={tokens[-1]}")
            records: List[ET.Element] = []
            for q in queries:
                records = self._sru(q, 10)
                if records:
                    break
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

    def fetch_covers(self, query: str, library_type: str = "Book") -> List[Dict[str, str]]:
        return []

    def _sru(self, cql: str, maximum: int) -> List[ET.Element]:
        res = _throttled_get(
            self,
            requests,
            _SRU,
            params={
                "version": "1.2",
                "operation": "searchRetrieve",
                "query": cql,
                "maximumRecords": str(max(1, min(maximum, 20))),
                "recordSchema": "dc",
                "startRecord": "1",
            },
            timeout=30,
            headers={"Accept": "application/xml"},
        )
        if res.status_code != 200:
            return []
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            return []
        out: List[ET.Element] = []
        for rd in root.findall(".//{http://www.loc.gov/zing/srw/}recordData"):
            dc = None
            for child in list(rd):
                tag = (child.tag or "").lower()
                if tag.endswith("}dc") or tag == "dc" or "srw_dc" in tag or "oai_dc" in tag:
                    dc = child
                    break
            if dc is None:
                # children already dc:* under recordData
                for child in rd.iter():
                    if (child.tag or "").endswith("}title") or child.tag == "title":
                        dc = rd
                        break
            if dc is not None:
                out.append(dc)
        return out

    def _dc_to_candidate(self, dc: ET.Element) -> Optional[Dict[str, Any]]:
        def texts(local: str) -> List[str]:
            vals = []
            for el in dc.iter():
                if el.tag.endswith("}" + local) or el.tag == local:
                    t = (el.text or "").strip()
                    if t:
                        vals.append(t)
            return vals

        titles = texts("title")
        if not titles:
            return None
        title = titles[0].split(" / ", 1)[0].strip()
        creators = texts("creator") + texts("contributor")
        staff = [
            {"role": "Story", "node": {"name": {"full": n}}} for n in creators[:5]
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
        url = None
        for ident in texts("identifier"):
            if ident.startswith("http"):
                url = ident
                break
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
            "url": url or _PORTAL,
            "links": [url] if url else [],
            "isbn": isbn,
        }
