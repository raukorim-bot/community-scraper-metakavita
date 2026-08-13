"""KB (Koninklijke Bibliotheek, NL) — livres NL via SRU JSRU / collection GGC."""
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

_SRU = "https://jsru.kb.nl/sru/sru"
_PORTAL = "https://www.kb.nl"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_NON_ISBN = re.compile(r"[^0-9Xx]")


def _norm_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = _NON_ISBN.sub("", str(raw)).upper()
    return c if len(c) in (10, 13) else None


def _cql_escape(term: str) -> str:
    return term.replace("\\", "\\\\").replace('"', '\\"')


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


class KbScraper(BaseScraper):
    id = "KB"
    display_name = "KB (Nederland)"
    supported_types = {"Book"}
    # 1.1.0 : `_sru` interroge deux collections à la suite (GGC puis DPO) et le
    # faisait sans cadence entre les deux. Toutes les requêtes y passent
    # désormais.
    version = "1.1.0"
    rate_limit = 1.5
    proxy_domains = ["kb.nl", "jsru.kb.nl", "www.kb.nl", "resolver.kb.nl"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [KB] Recherche pour '{0}'…",
            "search_isbn": "🔎 [KB] ISBN {0}…",
            "direct_id": "🎯 [KB] id={0}",
            "no_match": "⚠️ [KB] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [KB] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [KB] Erreur : {0}",
            "covers_err": "❌ [Covers] KB : pas d'images natives SRU",
        },
        "en": {
            "search_title": "🔍 [KB] Searching for '{0}'…",
            "search_isbn": "🔎 [KB] ISBN {0}…",
            "direct_id": "🎯 [KB] id={0}",
            "no_match": "⚠️ [KB] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [KB] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [KB] Error: {0}",
            "covers_err": "❌ [Covers] KB: no native SRU covers",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = url.strip()
        if re.fullmatch(r"[a-zA-Z0-9:_-]+", raw):
            return raw
        m = re.search(r"(?:urn:nbn:nl:[^\s]+|ppn[=/:](\d+))", raw, re.I)
        if m:
            return m.group(0) if m.lastindex is None or not m.group(1) else m.group(1)
        return None

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
                records = self._sru(f'"{_cql_escape(rid)}"', 5)
                for rec in records:
                    cand = self._dc_to_candidate(rec)
                    if cand:
                        return attach_match_score(cand, 1.0)
                return None

            existing_isbn = _norm_isbn((existing_metadata or {}).get("isbn"))
            cleaned = clean_title(query, library_type=library_type)
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                records = self._sru(f"isbn={existing_isbn}", 5)
                if not records:
                    records = self._sru(f'"{existing_isbn}"', 5)
                for rec in records:
                    cand = self._dc_to_candidate(rec)
                    if cand:
                        return attach_match_score(cand, 1.0)

            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            records = self._sru(f'title="{_cql_escape(cleaned)}"', 10)
            if not records:
                records = self._sru(f'"{_cql_escape(cleaned)}"', 10)
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

    def _sru(self, query: str, maximum: int) -> List[ET.Element]:
        # GGC = catalogage partagé NL ; fallback DPO si vide
        for collection in ("GGC", "DPO"):
            res = _throttled_get(
                self,
                requests,
                _SRU,
                params={
                    "version": "1.2",
                    "operation": "searchRetrieve",
                    "x-collection": collection,
                    "query": query,
                    "maximumRecords": str(max(1, min(maximum, 20))),
                    "recordSchema": "dc",
                },
                timeout=30,
                headers={"Accept": "application/xml"},
            )
            if res.status_code != 200:
                continue
            try:
                root = ET.fromstring(res.content)
            except ET.ParseError:
                continue
            out: List[ET.Element] = []
            for rd in root.findall(".//{http://www.loc.gov/zing/srw/}recordData"):
                dc = None
                for child in list(rd):
                    if child.tag.endswith("}dc") or child.tag == "dc":
                        dc = child
                        break
                if dc is None and rd.find("{http://purl.org/dc/elements/1.1/}title") is not None:
                    dc = rd
                if dc is not None:
                    out.append(dc)
            if out:
                return out
        return []

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
