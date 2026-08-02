"""WEBTOON (Line) — métadonnées webtoons / manhwa (HTML)."""
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

_BASE = "https://www.webtoons.com"
_TITLE_NO = re.compile(r"title_no=(\d+)")


class WebtoonScraper(BaseScraper):
    id = "WEBTOON"
    display_name = "WEBTOON"
    supported_types = {"Manga"}
    rate_limit = 1.2
    proxy_domains = [
        "webtoons.com",
        "www.webtoons.com",
        "swebtoon-phinf.pstatic.net",
        "webtoon-phinf.pstatic.net",
    ]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [WEBTOON] Recherche pour '{0}'…",
            "direct_id": "🎯 [WEBTOON] title_no={0}",
            "no_match": "⚠️ [WEBTOON] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [WEBTOON] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [WEBTOON] Erreur : {0}",
            "covers_err": "❌ [Covers] WEBTOON : {0}",
        },
        "en": {
            "search_title": "🔍 [WEBTOON] Searching for '{0}'…",
            "direct_id": "🎯 [WEBTOON] title_no={0}",
            "no_match": "⚠️ [WEBTOON] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [WEBTOON] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [WEBTOON] Error: {0}",
            "covers_err": "❌ [Covers] WEBTOON: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        if url.strip().isdigit():
            return url.strip()
        m = _TITLE_NO.search(url)
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Manga",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        session.headers.update({"Accept-Language": "en-US,en;q=0.9", "Referer": f"{_BASE}/en/"})
        try:
            if is_id:
                tid = self.extract_id_from_url(query)
                logging.info(self.t("direct_id").format(tid or query))
                if "webtoons.com" in query:
                    cand = self._parse_title(session, query)
                    return attach_match_score(cand, 1.0) if cand else None
                # sans URL complète on ne peut pas reconstruire le slug genre
                hits = self._search(session, query)
                for h in hits:
                    if self.extract_id_from_url(h["url"]) == tid:
                        cand = self._parse_title(session, h["url"])
                        return attach_match_score(cand, 1.0) if cand else None
                return None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(session, cleaned)
            # Préférer originals (pas canvas fan)
            hits.sort(key=lambda h: (0 if "/canvas/" not in h["url"] else 1, h["title"]))
            best, best_score = None, -1.0
            for hit in hits[:6]:
                cand = self._parse_title(session, hit["url"])
                if not cand:
                    cand = {
                        "title": hit["title"],
                        "url": hit["url"],
                        "links": [hit["url"]],
                        "format": "webtoon",
                        "genres": ["Manga"],
                        "tags": [],
                        "staff": [],
                        "summary": "",
                        "cover_url": None,
                        "alternative_titles": [],
                    }
                score = score_candidate(cand, cleaned, existing_metadata)
                if "/canvas/" in (cand.get("url") or ""):
                    score = max(0.0, score - 0.15)
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
                cand = self._parse_title(session, hit["url"])
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

    def _search(self, session, terms: str) -> List[dict]:
        res = session.get(
            f"{_BASE}/en/search", params={"keyword": terms}, timeout=25
        )
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, "html.parser")
        hits, seen = [], set()
        for a in soup.select('a[href*="title_no="]'):
            href = a.get("href") or ""
            tid = self.extract_id_from_url(href)
            if not tid or tid in seen:
                continue
            seen.add(tid)
            title = a.get_text(" ", strip=True)
            # "Tower of God SIU 1B Views" / "Title Author 588M Views"
            title = re.sub(
                r"\s+\S+\s+[\d.]+[KMB]?\s*Views.*$", "", title, flags=re.I
            ).strip()
            title = re.split(r"\s{2,}|\d+[KMB]?\s*Views", title)[0].strip()
            if not title:
                continue
            hits.append(
                {
                    "title": title,
                    "url": urljoin(_BASE, href),
                    "is_canvas": "/canvas/" in href,
                }
            )
            if len(hits) >= 15:
                break
        # Prefer originals over canvas fan works
        hits.sort(key=lambda h: (1 if h.get("is_canvas") else 0, h["title"]))
        return hits

    def _parse_title(self, session, url: str) -> Optional[Dict[str, Any]]:
        res = session.get(url, timeout=25)
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
        # Auteur souvent dans .author_area / .info .author
        authors = []
        for sel in (".author_area a", ".info .author", "a.author", ".detail_header .author"):
            for el in soup.select(sel):
                n = el.get_text(" ", strip=True)
                if n and n not in authors:
                    authors.append(n)
        staff = [
            {"role": "Story & Art", "node": {"name": {"full": n}}} for n in authors[:3]
        ]
        # Genre depuis URL /en/{genre}/...
        genres = []
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "en" and parts[1] not in {"search", "canvas"}:
            genres.append(parts[1].replace("-", " ").title())
        fmt = "webtoon"
        return {
            "title": title,
            "alternative_titles": [],
            "summary": (og_desc.get("content") if og_desc else "") or "",
            "cover_url": og_img.get("content") if og_img else None,
            "genres": (genres or ["Manga"])[: get_max_genres()],
            "tags": [],
            "year": None,
            "staff": staff,
            "format": fmt,
            "url": url.split("#")[0],
            "links": [url.split("#")[0]],
            # Pas de status inventé (BF59) — le HTML WEBTOON ne le donne pas de façon fiable
        }
