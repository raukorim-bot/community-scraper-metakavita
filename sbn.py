"""SBN / ICCU (Italia) — livres IT via API JSON OPAC mobile (sans clé).

Endpoint public utilisé par l’app OPAC SBN :
  https://opac.sbn.it/opacmobilegw/search.json
  https://opac.sbn.it/opacmobilegw/full.json
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_SEARCH = "https://opac.sbn.it/opacmobilegw/search.json"
_FULL = "https://opac.sbn.it/opacmobilegw/full.json"
_PORTAL = "https://opac.sbn.it"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_NON_ISBN = re.compile(r"[^0-9Xx]")
_BID = re.compile(r"(IT\\ICCU\\[A-Z0-9]+\\\d+|IT/ICCU/[A-Z0-9]+/\d+)", re.I)


def _norm_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = _NON_ISBN.sub("", str(raw)).upper()
    return c if len(c) in (10, 13) else None


def _norm_bid(raw: str) -> str:
    # IT\ICCU\XXX\123 → keep single backslashes for API
    b = raw.strip()
    b = b.replace("/", "\\")
    b = b.replace("\\\\", "\\")
    return b


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


class SbnScraper(BaseScraper):
    id = "SBN"
    display_name = "SBN (Italia)"
    supported_types = {"Book"}
    # 1.1.0 : `_get`, point de passage unique des appels OPAC, applique
    # désormais la cadence — elle ne l'était qu'une fois par `fetch()`.
    version = "1.1.0"
    rate_limit = 1.5
    proxy_domains = ["sbn.it", "opac.sbn.it", "www.sbn.it", "iccu.sbn.it"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [SBN] Recherche pour '{0}'…",
            "search_isbn": "🔎 [SBN] ISBN {0}…",
            "direct_id": "🎯 [SBN] BID={0}",
            "no_match": "⚠️ [SBN] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [SBN] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [SBN] Erreur : {0}",
            "covers_err": "❌ [Covers] SBN : pas de covers natives",
        },
        "en": {
            "search_title": "🔍 [SBN] Searching for '{0}'…",
            "search_isbn": "🔎 [SBN] ISBN {0}…",
            "direct_id": "🎯 [SBN] BID={0}",
            "no_match": "⚠️ [SBN] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [SBN] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [SBN] Error: {0}",
            "covers_err": "❌ [Covers] SBN: no native covers",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        m = _BID.search(url.replace("%5C", "\\"))
        if m:
            return _norm_bid(m.group(1))
        if "ICCU" in url.upper():
            return _norm_bid(url.strip())
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
                bid = self.extract_id_from_url(query) or _norm_bid(query)
                logging.info(self.t("direct_id").format(bid))
                full = self._full(bid)
                cand = self._full_to_cand(full, bid) if full else None
                return attach_match_score(cand, 1.0) if cand else None

            existing_isbn = _norm_isbn((existing_metadata or {}).get("isbn"))
            cleaned = clean_title(query, library_type=library_type)
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                hits = self._search_isbn(existing_isbn)
                for hit in hits:
                    cand = self._hit_to_cand(hit)
                    if not cand:
                        continue
                    enriched = self._enrich(cand)
                    return attach_match_score(enriched or cand, 1.0)

            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search_any(cleaned)
            best, best_score = None, -1.0
            for hit in hits[:10]:
                cand = self._hit_to_cand(hit)
                if not cand:
                    continue
                score = score_candidate(cand, cleaned, existing_metadata)
                if score > best_score:
                    best_score, best = score, cand
            if not best or best_score < get_match_accept_threshold():
                logging.warning(
                    self.t("no_match").format(cleaned, int(max(best_score, 0) * 100))
                )
                return None
            best = self._enrich(best) or best
            logging.info(self.t("matched").format(best.get("title"), int(best_score * 100)))
            return attach_match_score(best, best_score)
        except Exception as e:
            logging.error(self.t("err").format(e))
            return None

    def fetch_covers(self, query: str, library_type: str = "Book") -> List[Dict[str, str]]:
        return []

    def _get(self, url: str, params: dict) -> Any:
        res = _throttled_get(
            self,
            requests,
            url,
            params=params,
            timeout=25,
            headers={"Accept": "application/json"},
        )
        if res.status_code != 200:
            return None
        try:
            return res.json()
        except Exception:
            return None

    def _search_any(self, terms: str) -> List[dict]:
        data = self._get(_SEARCH, {"any": terms, "type": 0, "start": 0, "rows": 10})
        return self._extract_docs(data)

    def _search_isbn(self, isbn: str) -> List[dict]:
        data = self._get(_SEARCH, {"isbn": isbn})
        return self._extract_docs(data)

    def _extract_docs(self, data: Any) -> List[dict]:
        if not isinstance(data, dict):
            return []
        for key in ("briefRecords", "docs", "documenti", "results", "response"):
            val = data.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
            if isinstance(val, dict) and isinstance(val.get("docs"), list):
                return [x for x in val["docs"] if isinstance(x, dict)]
        brief = data.get("brief")
        if isinstance(brief, list):
            return [x for x in brief if isinstance(x, dict)]
        return []

    def _full(self, bid: str) -> Optional[dict]:
        data = self._get(_FULL, {"bid": bid})
        return data if isinstance(data, dict) else None

    def _enrich(self, cand: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        bid = cand.get("_bid")
        if not bid:
            return cand
        full = self._full(str(bid))
        if not full:
            return cand
        richer = self._full_to_cand(full, str(bid))
        if not richer:
            return cand
        # keep search cover/url if fuller missing
        if not richer.get("summary") and cand.get("summary"):
            richer["summary"] = cand["summary"]
        return richer

    def _hit_to_cand(self, hit: dict) -> Optional[Dict[str, Any]]:
        title = (
            hit.get("titolo")
            or hit.get("title")
            or hit.get("titoloProprio")
            or hit.get("titolo_proprio")
        )
        if not title:
            return None
        # "il nome della rosa / Umberto Eco" → titre seul
        title = str(title).split(" / ", 1)[0].strip()
        title = re.sub(r"[\x98\x9c\x88\x89]", "", title)
        title = re.sub(r"\s+", " ", title).strip(" .,;:")
        bid = (
            hit.get("codiceIdentificativo")
            or hit.get("bid")
            or hit.get("id")
            or hit.get("codice_identificativo")
        )
        if bid:
            bid = _norm_bid(str(bid))
        authors = (
            hit.get("autorePrincipale")
            or hit.get("autore")
            or hit.get("autori")
            or hit.get("author")
            or []
        )
        if isinstance(authors, str):
            authors = [authors]
        staff = [
            {"role": "Story", "node": {"name": {"full": str(a)}}}
            for a in authors[:5]
            if a
        ]
        year = None
        for key in ("pubblicazione", "dataPubblicazione", "date", "anno", "pubDate"):
            m = _YEAR.search(str(hit.get(key) or ""))
            if m:
                year = int(m.group(1))
                break
        isbn = _norm_isbn(hit.get("isbn") or hit.get("ISBN"))
        publisher = hit.get("editore") or hit.get("publisher")
        if not publisher and hit.get("pubblicazione"):
            # "Milano : Bompiani, 1988"
            pub = str(hit["pubblicazione"])
            if ":" in pub:
                publisher = pub.split(":", 1)[1].split(",", 1)[0].strip()
        url = f"{_PORTAL}/" if not bid else f"{_PORTAL}/risultati-ricerca-avanzata?bid={quote(bid)}"
        cand = {
            "title": title,
            "alternative_titles": [],
            "summary": str(hit.get("descrizione") or hit.get("description") or ""),
            "cover_url": None,
            "genres": ["Book"][: get_max_genres()],
            "tags": [],
            "year": year,
            "staff": staff,
            "publisher": publisher,
            "format": "book",
            "url": url,
            "links": [url],
            "isbn": isbn,
            "_bid": bid,
        }
        return cand

    def _full_to_cand(self, full: dict, bid: str) -> Optional[Dict[str, Any]]:
        # full payload may nest under 'documento' / 'notice'
        doc = full.get("documento") or full.get("notice") or full
        if not isinstance(doc, dict):
            return None
        hit = dict(doc)
        hit.setdefault("codiceIdentificativo", bid)
        return self._hit_to_cand(hit)
