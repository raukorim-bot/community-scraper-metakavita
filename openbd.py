"""openBD (JP) — métadonnées / covers livres japonais via API ISBN (gratuit, sans clé).

API : https://api.openbd.jp/v1/get?isbn=…
Recherche par titre non supportée par l’API → ISBN requis (query ou existing_metadata).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional

from curl_cffi import requests

from config_manager import get_max_genres
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_API = "https://api.openbd.jp/v1/get"
_NON_ISBN = re.compile(r"[^0-9Xx]")
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


def _norm_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = _NON_ISBN.sub("", str(raw)).upper()
    return c if len(c) in (10, 13) else None


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


class OpenbdScraper(BaseScraper):
    id = "OPENBD"
    display_name = "openBD (JP)"
    supported_types = {"Book"}
    # 1.1.0 : `_get_isbn` applique désormais la cadence. `fetch_covers` en
    # enchaîne un par ISBN candidat, sans aucune pause jusqu'ici.
    version = "1.1.0"
    rate_limit = 0.4  # bulk API, no hard limit — polite 0.4s
    proxy_domains = [
        "openbd.jp",
        "api.openbd.jp",
        "cover.openbd.jp",
        "www.openbd.jp",
    ]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_isbn": "🔎 [openBD] ISBN {0}…",
            "no_isbn": "⚠️ [openBD] ISBN requis (API ISBN-only)",
            "no_match": "⚠️ [openBD] Aucun résultat pour ISBN {0}",
            "matched": "🎯 [openBD] Match : '{0}'",
            "err": "❌ [openBD] Erreur : {0}",
            "covers_err": "❌ [Covers] openBD : {0}",
        },
        "en": {
            "search_isbn": "🔎 [openBD] ISBN {0}…",
            "no_isbn": "⚠️ [openBD] ISBN required (ISBN-only API)",
            "no_match": "⚠️ [openBD] No result for ISBN {0}",
            "matched": "🎯 [openBD] Match: '{0}'",
            "err": "❌ [openBD] Error: {0}",
            "covers_err": "❌ [Covers] openBD: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        return _norm_isbn(url.strip())

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            isbn = None
            if is_id:
                isbn = self.extract_id_from_url(query) or _norm_isbn(query)
            if not isbn:
                isbn = _norm_isbn((existing_metadata or {}).get("isbn"))
            if not isbn:
                isbn = _norm_isbn(query)
            if not isbn:
                logging.warning(self.t("no_isbn"))
                return None

            logging.info(self.t("search_isbn").format(isbn))
            cand = self._get_isbn(isbn)
            if not cand:
                logging.warning(self.t("no_match").format(isbn))
                return None
            cleaned = clean_title(query, library_type=library_type) or cand.get("title") or ""
            score = 1.0 if is_id or _norm_isbn(query) == isbn else score_candidate(
                cand, cleaned, existing_metadata
            )
            if score < get_match_accept_threshold() and not is_id:
                logging.warning(
                    self.t("no_match").format(isbn)
                    + f" (score {int(score * 100)}%)"
                )
                return None
            logging.info(self.t("matched").format(cand.get("title")))
            return attach_match_score(cand, min(1.0, score))
        except Exception as e:
            logging.error(self.t("err").format(e))
            return None

    def fetch_covers(self, query: str, library_type: str = "Book") -> List[Dict[str, str]]:
        covers: List[Dict[str, str]] = []
        isbn = _norm_isbn(query)
        if not isbn:
            return covers
        try:
            cand = self._get_isbn(isbn)
            if cand and cand.get("cover_url"):
                covers.append(
                    {
                        "provider": self.display_name,
                        "title": cand.get("title") or isbn,
                        "url": cand["cover_url"],
                    }
                )
        except Exception as e:
            logging.error(self.t("covers_err").format(e))
        return covers

    def _get_isbn(self, isbn: str) -> Optional[Dict[str, Any]]:
        res = _throttled_get(self, requests, _API, params={"isbn": isbn}, timeout=20)
        if res.status_code != 200:
            return None
        data = res.json()
        if not isinstance(data, list) or not data or not data[0]:
            return None
        row = data[0]
        summary = row.get("summary") if isinstance(row, dict) else None
        onix = row.get("onix") if isinstance(row, dict) else None
        title = None
        author = None
        publisher = None
        pubdate = None
        cover = None
        if isinstance(summary, dict):
            title = summary.get("title")
            author = summary.get("author")
            publisher = summary.get("publisher")
            pubdate = summary.get("pubdate")
            cover = summary.get("cover")
        if not title and isinstance(onix, dict):
            try:
                title = (
                    onix["DescriptiveDetail"]["TitleDetail"]["TitleElement"]["TitleText"]
                )
                if isinstance(title, dict):
                    title = title.get("content") or title.get("#text") or str(title)
            except Exception:
                title = None
        if not title:
            return None
        year = None
        if pubdate:
            m = _YEAR.search(str(pubdate))
            if m:
                year = int(m.group(1))
        staff = []
        if author:
            # "Surname/FirstName" or "A, B"
            for part in re.split(r"[,;/]", str(author)):
                name = part.strip().replace("／", " ").replace("/", " ").strip()
                if name:
                    staff.append({"role": "Story", "node": {"name": {"full": name}}})
        # Ne pas inventer cover.openbd.jp/{isbn}.jpg : beaucoup d'ISBN n'ont
        # pas d'image (404) → vignette cassée dans Manual Review / covers.
        if cover and not str(cover).startswith(("http://", "https://")):
            cover = None
        url = f"https://www.openbd.jp/"  # pas d'URL notice stable ; ISBN en id
        return {
            "title": str(title).strip(),
            "alternative_titles": [],
            "summary": "",
            "cover_url": cover or None,
            "genres": ["Book"][: get_max_genres()],
            "tags": [],
            "year": year,
            "staff": staff[:5],
            "publisher": publisher,
            "format": "book",
            "url": url,
            "links": [url],
            "isbn": isbn,
        }
