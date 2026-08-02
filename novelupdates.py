"""Novel Updates — light novels / novels (HTML, Cloudflare optionnel).

Sans cookies CF, le site renvoie souvent le challenge JS.
Configurer via NOVELUPDATES_API_KEY (détournement du champ clé) :
  cf_clearance=<token>; __cf_bm=<token>
ou coller une chaîne Cookie complète exportée du navigateur.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags, load_config
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_BASE = "https://www.novelupdates.com"
_SERIES = re.compile(r"^/series/([^/?#]+)/?", re.I)


def _nu_cookies() -> str:
    # Slot clé MetaKavita / env pour coller les cookies CF
    cfg = {}
    try:
        cfg = load_config() or {}
    except Exception:
        cfg = {}
    for key in ("NOVELUPDATES_API_KEY", "NOVELUPDATES_COOKIES", "CF_CLEARANCE"):
        val = (cfg.get(key) or os.environ.get(key) or "").strip()
        if val:
            if key == "CF_CLEARANCE" and "=" not in val:
                return f"cf_clearance={val}"
            return val
    return ""


class NovelUpdatesScraper(BaseScraper):
    id = "NOVELUPDATES"
    display_name = "Novel Updates"
    supported_types = {"Book", "Manga"}
    rate_limit = 3.0  # HTML + Cloudflare — anti-ban IP
    proxy_domains = ["novelupdates.com", "www.novelupdates.com"]
    has_direct_id_support = True
    needs_api_key = False  # cookies optionnels via env / clé UI
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [Novel Updates] Recherche pour '{0}'…",
            "direct_id": "🎯 [Novel Updates] slug={0}",
            "no_match": "⚠️ [Novel Updates] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Novel Updates] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Novel Updates] Erreur : {0}",
            "covers_err": "❌ [Covers] Novel Updates : {0}",
            "cf": "⚠️ [Novel Updates] Bloqué par Cloudflare — collez cf_clearance dans NOVELUPDATES_API_KEY",
        },
        "en": {
            "search_title": "🔍 [Novel Updates] Searching for '{0}'…",
            "direct_id": "🎯 [Novel Updates] slug={0}",
            "no_match": "⚠️ [Novel Updates] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Novel Updates] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Novel Updates] Error: {0}",
            "covers_err": "❌ [Covers] Novel Updates: {0}",
            "cf": "⚠️ [Novel Updates] Cloudflare blocked — paste cf_clearance into NOVELUPDATES_API_KEY",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        path = urlparse(url).path if "://" in url else url
        m = _SERIES.match(path if path.startswith("/") else f"/series/{path}")
        return m.group(1) if m else None

    def _session(self):
        session = requests.Session(impersonate="chrome110")
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{_BASE}/",
        }
        cookies = _nu_cookies()
        if cookies:
            headers["Cookie"] = cookies
        session.headers.update(headers)
        return session

    def _is_cf(self, text: str) -> bool:
        low = (text or "")[:800].casefold()
        return "just a moment" in low or "cf-challenge" in low or "checking your browser" in low

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = self._session()
        try:
            if is_id:
                slug = self.extract_id_from_url(query)
                if not slug:
                    return None
                logging.info(self.t("direct_id").format(slug))
                cand = self._parse_series(session, f"{_BASE}/series/{slug}/")
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(session, cleaned)
            if hits is None:
                return None
            best, best_score = None, -1.0
            for hit in hits[:6]:
                cand = self._parse_series(session, hit["url"])
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
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        session = self._session()
        try:
            hits = self._search(session, cleaned) or []
            for hit in hits[:5]:
                cand = self._parse_series(session, hit["url"])
                url = (cand or {}).get("cover_url")
                if url:
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": (cand or hit).get("title") or cleaned,
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

    def _search(self, session, terms: str) -> Optional[List[dict]]:
        res = session.get(
            f"{_BASE}/",
            params={"s": terms, "post_type": "seriesplans"},
            timeout=25,
        )
        if self._is_cf(res.text) or res.status_code in (403, 503):
            logging.warning(self.t("cf"))
            return None
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, "html.parser")
        hits, seen = [], set()
        for a in soup.select('a[href*="/series/"]'):
            href = a.get("href") or ""
            slug = self.extract_id_from_url(href)
            if not slug or slug in seen:
                continue
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 2:
                continue
            seen.add(slug)
            hits.append({"title": title, "url": f"{_BASE}/series/{slug}/"})
            if len(hits) >= 12:
                break
        return hits

    def _parse_series(self, session, url: str) -> Optional[Dict[str, Any]]:
        res = session.get(url, timeout=25)
        if self._is_cf(res.text) or res.status_code != 200:
            if self._is_cf(res.text):
                logging.warning(self.t("cf"))
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        title_el = soup.select_one(".seriestitlenu") or soup.select_one("h1")
        title = title_el.get_text(" ", strip=True) if title_el else ""
        if not title:
            return None
        desc = soup.select_one("#editdescription")
        summary = desc.get_text("\n", strip=True) if desc else ""
        genres = [
            a.get_text(" ", strip=True)
            for a in soup.select("#seriesgenre a")
            if a.get_text(strip=True)
        ]
        tags = [
            a.get_text(" ", strip=True)
            for a in soup.select("#showtags a")
            if a.get_text(strip=True)
        ]
        authors = [
            a.get_text(" ", strip=True)
            for a in soup.select("#showauthors a")
            if a.get_text(strip=True)
        ]
        staff = [
            {"role": "Story", "node": {"name": {"full": n}}} for n in authors[:4]
        ]
        img = soup.select_one(".seriesimg img") or soup.select_one('meta[property="og:image"]')
        cover = None
        if img:
            cover = img.get("src") or img.get("content")
        return {
            "title": title,
            "alternative_titles": [],
            "summary": summary,
            "cover_url": cover,
            "genres": (genres or ["Novel"])[: get_max_genres()],
            "tags": tags[: get_max_tags()],
            "year": None,
            "staff": staff,
            "format": "novel",
            "url": url.split("?")[0],
            "links": [url.split("?")[0]],
        }
