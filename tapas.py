"""Tapas — webcomics / manhwa (HTML search + série)."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from config_manager import get_max_genres
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_BASE = "https://tapas.io"
_SERIES = re.compile(r"^/series/([^/?#]+)", re.I)


class TapasScraper(BaseScraper):
    id = "TAPAS"
    display_name = "Tapas"
    supported_types = {"Manga"}
    rate_limit = 1.2
    proxy_domains = ["tapas.io", "www.tapas.io", "s3.tapasticusercontent.com", "tapas-prod.s3.amazonaws.com"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [Tapas] Recherche pour '{0}'…",
            "direct_id": "🎯 [Tapas] series={0}",
            "no_match": "⚠️ [Tapas] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Tapas] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Tapas] Erreur : {0}",
            "covers_err": "❌ [Covers] Tapas : {0}",
        },
        "en": {
            "search_title": "🔍 [Tapas] Searching for '{0}'…",
            "direct_id": "🎯 [Tapas] series={0}",
            "no_match": "⚠️ [Tapas] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Tapas] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Tapas] Error: {0}",
            "covers_err": "❌ [Covers] Tapas: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        path = urlparse(url).path if "://" in url else url
        m = _SERIES.match(path if path.startswith("/") else f"/series/{path}")
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Manga",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        session.headers.update({"Accept-Language": "en-US,en;q=0.9", "Referer": f"{_BASE}/"})
        try:
            if is_id:
                slug = self.extract_id_from_url(query)
                if not slug:
                    return None
                logging.info(self.t("direct_id").format(slug))
                cand = self._parse_series(session, f"{_BASE}/series/{slug}")
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(session, cleaned)
            best, best_score = None, -1.0
            for hit in hits[:6]:
                cand = self._parse_series(session, hit["url"]) or {
                    "title": hit["title"],
                    "url": hit["url"],
                    "links": [hit["url"]],
                    "format": "webtoon",
                    "genres": ["Manga"],
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

    def fetch_covers(self, query: str, library_type: str = "Manga") -> List[Dict[str, str]]:
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
        res = session.get(
            f"{_BASE}/search", params={"q": terms, "t": "SERIES"}, timeout=25
        )
        if res.status_code != 200:
            # fallback sans t=
            res = session.get(f"{_BASE}/search", params={"q": terms}, timeout=25)
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
            img = a.select_one("img")
            cover = None
            if img:
                cover = img.get("src") or img.get("data-src")
            hits.append(
                {
                    "title": title,
                    "url": f"{_BASE}/series/{slug}",
                    "cover": cover,
                }
            )
            if len(hits) >= 12:
                break
        return hits

    def _parse_series(self, session, url: str) -> Optional[Dict[str, Any]]:
        res = session.get(url, timeout=25)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        og_title = soup.select_one('meta[property="og:title"]')
        og_desc = soup.select_one('meta[property="og:description"]')
        og_img = soup.select_one('meta[property="og:image"]')
        title = (og_title.get("content") if og_title else "").strip()
        # "Read Solo Leveling | Tapas Web Comics"
        title = re.sub(r"^Read\s+", "", title, flags=re.I).strip()
        title = re.sub(r"\s*\|\s*Tapas.*$", "", title, flags=re.I).strip()
        if not title and soup.h1:
            title = soup.h1.get_text(" ", strip=True)
        if not title or title.casefold().startswith("tapas"):
            return None
        authors = []
        for sel in (".creator-name", "a.name", ".author-name", ".info-body a"):
            for el in soup.select(sel):
                n = el.get_text(" ", strip=True)
                if n and n not in authors and len(n) < 80:
                    authors.append(n)
        staff = [
            {"role": "Story & Art", "node": {"name": {"full": n}}} for n in authors[:3]
        ]
        summary = (og_desc.get("content") if og_desc else "") or ""
        # og:description est souvent le pitch marketing Tapas, pas le résumé série
        if "only on tapas" in summary.casefold() or "discover stories" in summary.casefold():
            summary = ""
        return {
            "title": title,
            "alternative_titles": [],
            "summary": summary,
            "cover_url": og_img.get("content") if og_img else None,
            "genres": ["Manga"][: get_max_genres()],
            "tags": [],
            "year": None,
            "staff": staff,
            "format": "webtoon",
            "url": url.split("?")[0],
            "links": [url.split("?")[0]],
        }
