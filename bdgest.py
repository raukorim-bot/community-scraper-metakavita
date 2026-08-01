"""BDgest / Bedetheque search mirror — best-effort HTML BD FR.

Note: la recherche native BDgest est souvent JS-heavy ; on tente
plusieurs URLs et on parse les liens série bedetheque/bdgest si présents.
Qualité de matching à finetuner plus tard.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_BASE = "https://www.bdgest.com"
_SERIES = re.compile(
    r"(?:bedetheque\.com|bdgest\.com)/(?:serie|series)/([^/?#]+)",
    re.I,
)
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


class BdgestScraper(BaseScraper):
    id = "BDGEST"
    display_name = "BDgest"
    supported_types = {"Comic"}
    rate_limit = 1.5
    proxy_domains = [
        "bdgest.com",
        "www.bdgest.com",
        "bedetheque.com",
        "www.bedetheque.com",
    ]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [BDgest] Recherche pour '{0}'…",
            "direct_id": "🎯 [BDgest] serie={0}",
            "no_match": "⚠️ [BDgest] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [BDgest] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [BDgest] Erreur : {0}",
            "covers_err": "❌ [Covers] BDgest : {0}",
        },
        "en": {
            "search_title": "🔍 [BDgest] Searching for '{0}'…",
            "direct_id": "🎯 [BDgest] series={0}",
            "no_match": "⚠️ [BDgest] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [BDgest] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [BDgest] Error: {0}",
            "covers_err": "❌ [Covers] BDgest: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        m = _SERIES.search(url)
        if m:
            return m.group(1)
        path = urlparse(url).path if "://" in url else url
        parts = [p for p in path.split("/") if p]
        if parts and re.fullmatch(r"[a-z0-9\-]+", parts[-1], re.I):
            return parts[-1]
        return None

    def fetch(
        self,
        query: str,
        library_type: str = "Comic",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        session.headers.update(
            {"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5", "Referer": f"{_BASE}/"}
        )
        try:
            if is_id:
                slug = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(slug))
                for url in (
                    query if "://" in query else None,
                    f"{_BASE}/serie/{slug}",
                    f"https://www.bedetheque.com/serie/{slug}",
                    f"https://www.bedetheque.com/serie-{slug}.html",
                ):
                    if not url:
                        continue
                    cand = self._parse_series(session, url)
                    if cand:
                        return attach_match_score(cand, 1.0)
                return None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(session, cleaned)
            best, best_score = None, -1.0
            for hit in hits[:6]:
                cand = self._parse_series(session, hit["url"])
                if not cand:
                    cand = {
                        "title": hit["title"],
                        "url": hit["url"],
                        "links": [hit["url"]],
                        "format": "comic",
                        "genres": ["Comic"],
                        "tags": [],
                        "staff": [],
                        "summary": "",
                        "cover_url": hit.get("cover"),
                        "alternative_titles": [],
                    }
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

    def fetch_covers(self, query: str, library_type: str = "Comic") -> List[Dict[str, str]]:
        covers = []
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        session = requests.Session(impersonate="chrome110")
        try:
            for hit in self._search(session, cleaned)[:5]:
                cand = self._parse_series(session, hit["url"])
                url = (cand or {}).get("cover_url") or hit.get("cover")
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

    def _search(self, session, terms: str) -> List[dict]:
        candidates = [
            (f"{_BASE}/search", {"q": terms}),
            (f"{_BASE}/recherche", {"q": terms}),
            (f"{_BASE}/", {"searchsite": terms}),
            ("https://www.bedetheque.com/search/0", {"RechSerie": terms}),
            ("https://www.bedetheque.com/search/0", {"RechTout": terms}),
        ]
        hits, seen = [], set()
        for url, params in candidates:
            try:
                res = session.get(url, params=params, timeout=20)
                if res.status_code != 200 or len(res.text) < 500:
                    continue
                soup = BeautifulSoup(res.text, "html.parser")
                for a in soup.select('a[href*="serie"]'):
                    href = a.get("href") or ""
                    if "serie" not in href.casefold():
                        continue
                    full = urljoin(url, href)
                    key = full.split("?")[0]
                    if key in seen:
                        continue
                    title = a.get_text(" ", strip=True)
                    if not title or len(title) < 2:
                        continue
                    # Filtrer nav générique
                    if title.casefold() in {"série", "series", "bd", "comics"}:
                        continue
                    seen.add(key)
                    hits.append({"title": title, "url": key})
                    if len(hits) >= 12:
                        return hits
            except Exception:
                continue
        return hits

    def _parse_series(self, session, url: str) -> Optional[Dict[str, Any]]:
        try:
            res = session.get(url, timeout=25)
        except Exception:
            return None
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        og_title = soup.select_one('meta[property="og:title"]')
        og_desc = soup.select_one('meta[property="og:description"]')
        og_img = soup.select_one('meta[property="og:image"]')
        title = (og_title.get("content") if og_title else "").strip()
        if not title and soup.h1:
            title = soup.h1.get_text(" ", strip=True)
        if not title:
            return None
        title = re.sub(r"\s*[-|]\s*(BDgest|Bédéthèque|Bedetheque).*$", "", title, flags=re.I).strip()
        authors = []
        for sel in (".auteur a", ".infos a[href*='auteur']", "a[href*='/auteur']"):
            for el in soup.select(sel):
                n = el.get_text(" ", strip=True)
                if n and n not in authors and len(n) < 60:
                    authors.append(n)
        staff = [
            {"role": "Story & Art", "node": {"name": {"full": n}}} for n in authors[:4]
        ]
        year = None
        m = _YEAR.search(soup.get_text(" ", strip=True)[:2500])
        if m:
            y = int(m.group(1))
            if 1900 <= y <= 2030:
                year = y
        return {
            "title": title,
            "alternative_titles": [],
            "summary": (og_desc.get("content") if og_desc else "") or "",
            "cover_url": og_img.get("content") if og_img else None,
            "genres": ["Comic"][: get_max_genres()],
            "tags": [],
            "year": year,
            "staff": staff,
            "format": "comic",
            "url": url.split("?")[0],
            "links": [url.split("?")[0]],
        }
