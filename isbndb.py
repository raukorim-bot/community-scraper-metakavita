"""ISBNdb — métadonnées livres via API REST (clé requise).

Clé : ISBNDB_API_KEY (REST key depuis isbndb.com dashboard).
Header : Authorization: <REST_KEY>
Doc : https://isbndb.com/apidocs/v2
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags, load_config
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_API = "https://api2.isbndb.com"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_ISBN = re.compile(r"^(?:\d{9}[\dXx]|\d{13})$")

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


class IsbndbScraper(BaseScraper):
    id = "ISBNDB"
    display_name = "ISBNdb"
    supported_types = {"Book"}
    # 1.1.0 : toutes les requêtes d'un `fetch()` passent par la cadence. Le plan
    # Basic est facturé à la requête et coupé à 1/s : la rafale coûtait cher.
    version = "1.1.0"
    rate_limit = 1.1  # ~0.91/s: 10% under Basic plan 1/s
    proxy_domains = ["isbndb.com", "api2.isbndb.com", "images.isbndb.com"]
    has_direct_id_support = True
    needs_api_key = True
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [ISBNdb] Recherche pour '{0}'…",
            "direct_id": "🎯 [ISBNdb] isbn={0}",
            "no_match": "⚠️ [ISBNdb] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [ISBNdb] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [ISBNdb] Erreur : {0}",
            "covers_err": "❌ [Covers] ISBNdb : {0}",
            "nokey": "⚠️ [ISBNdb] Clé manquante — ISBNDB_API_KEY dans Config",
            "auth": "❌ [ISBNdb] Auth refusée (401) — vérifiez ISBNDB_API_KEY",
        },
        "en": {
            "search_title": "🔍 [ISBNdb] Searching for '{0}'…",
            "direct_id": "🎯 [ISBNdb] isbn={0}",
            "no_match": "⚠️ [ISBNdb] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [ISBNdb] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [ISBNdb] Error: {0}",
            "covers_err": "❌ [Covers] ISBNdb: {0}",
            "nokey": "⚠️ [ISBNdb] Missing key — set ISBNDB_API_KEY in Config",
            "auth": "❌ [ISBNdb] Auth rejected (401) — check ISBNDB_API_KEY",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = re.sub(r"[^0-9Xx]", "", url.strip())
        return raw.upper() if _ISBN.match(raw) else None

    def _api_key(self) -> Optional[str]:
        key = (load_config().get("ISBNDB_API_KEY") or "").strip()
        return key or None

    def _headers(self, key: str) -> Dict[str, str]:
        return {
            "Authorization": key,
            "Accept": "application/json",
            "User-Agent": "MetaKavita-community-scraper/1.0",
        }

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        key = self._api_key()
        if not key:
            logging.warning(self.t("nokey"))
            return None
        session = requests.Session(impersonate="chrome110")
        try:
            if is_id:
                isbn = self.extract_id_from_url(query) or re.sub(
                    r"[^0-9Xx]", "", query
                ).upper()
                if not isbn:
                    return None
                logging.info(self.t("direct_id").format(isbn))
                book = self._get_book(session, key, isbn)
                cand = self._book_to_cand(book) if book else None
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            books = self._search(session, key, cleaned)
            best, best_score = None, -1.0
            for book in books[:8]:
                cand = self._book_to_cand(book)
                if not cand:
                    continue
                score = score_candidate(cand, cleaned, existing_metadata)
                if (cand.get("title") or "").casefold() == cleaned.casefold():
                    score = min(1.0, score + 0.12)
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
        covers = []
        key = self._api_key()
        if not key:
            return covers
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        session = requests.Session(impersonate="chrome110")
        try:
            for book in self._search(session, key, cleaned)[:5]:
                cand = self._book_to_cand(book)
                url = (cand or {}).get("cover_url")
                if url:
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": (cand or {}).get("title") or cleaned,
                            "url": url,
                        }
                    )
        except Exception as e:
            logging.error(self.t("covers_err").format(e))
        finally:
            try:
                session.close()
            except Exception:
                pass
        return covers

    def _search(self, session, key: str, terms: str) -> List[dict]:
        res = _throttled_get(
            self,
            session,
            f"{_API}/books/{quote(terms)}",
            headers=self._headers(key),
            params={"page": 1, "pageSize": 20},
            timeout=25,
        )
        if res.status_code == 401:
            logging.error(self.t("auth"))
            return []
        if res.status_code != 200:
            return []
        data = res.json() if res.content else {}
        books = data.get("books") or data.get("data") or []
        return [b for b in books if isinstance(b, dict)]

    def _get_book(self, session, key: str, isbn: str) -> Optional[dict]:
        res = _throttled_get(
            self,
            session,
            f"{_API}/book/{isbn}",
            headers=self._headers(key),
            timeout=25,
        )
        if res.status_code == 401:
            logging.error(self.t("auth"))
            return None
        if res.status_code != 200:
            return None
        data = res.json() if res.content else {}
        book = data.get("book") if isinstance(data, dict) else None
        return book if isinstance(book, dict) else (data if isinstance(data, dict) else None)

    def _book_to_cand(self, book: dict) -> Optional[Dict[str, Any]]:
        title = (book.get("title") or book.get("title_long") or "").strip()
        if not title:
            return None
        authors = book.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        staff = [
            {"role": "Story", "node": {"name": {"full": str(a).strip()}}}
            for a in authors
            if a
        ][:6]
        year = None
        for key in ("date_published", "publish_date", "year"):
            raw = book.get(key)
            if raw:
                m = _YEAR.search(str(raw))
                if m:
                    year = int(m.group(1))
                    break
        isbn = book.get("isbn13") or book.get("isbn") or ""
        subjects = book.get("subjects") or book.get("subject") or []
        if isinstance(subjects, str):
            subjects = [subjects]
        genres = [str(s) for s in subjects if s][: get_max_genres()]
        cover = book.get("image") or book.get("image_original") or book.get("cover")
        url = f"https://isbndb.com/book/{isbn}" if isbn else None
        alts = []
        if book.get("title_long") and book.get("title_long") != title:
            alts.append(book["title_long"])
        return {
            "title": title,
            "alternative_titles": alts,
            "summary": (book.get("synopsis") or book.get("overview") or "") or "",
            "cover_url": cover,
            "genres": genres or ["Book"],
            "tags": [],
            "year": year,
            "staff": staff,
            "format": "book",
            "isbn": isbn or None,
            "url": url,
            "links": [url] if url else [],
            "publisher": book.get("publisher"),
        }
