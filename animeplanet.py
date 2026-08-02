"""Anime-Planet — métadonnées manga (HTML)."""
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

_BASE = "https://www.anime-planet.com"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_SLUG = re.compile(r"^/manga/([a-z0-9\-]+)/?$", re.I)


class AnimePlanetScraper(BaseScraper):
    id = "ANIMEPLANET"
    display_name = "Anime-Planet"
    supported_types = {"Manga"}
    rate_limit = 3.0  # HTML — anti-ban IP
    proxy_domains = ["anime-planet.com", "www.anime-planet.com", "cdn.anime-planet.com"]
    has_direct_id_support = True
    # CDN refuse le hotlink si Referer ≠ anime-planet.com (403 HTML).
    requires_proxy = True
    proxy_referer = "https://www.anime-planet.com/"
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [Anime-Planet] Recherche pour '{0}'…",
            "direct_id": "🎯 [Anime-Planet] slug={0}",
            "no_match": "⚠️ [Anime-Planet] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Anime-Planet] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Anime-Planet] Erreur : {0}",
            "covers_err": "❌ [Covers] Anime-Planet : {0}",
        },
        "en": {
            "search_title": "🔍 [Anime-Planet] Searching for '{0}'…",
            "direct_id": "🎯 [Anime-Planet] slug={0}",
            "no_match": "⚠️ [Anime-Planet] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Anime-Planet] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Anime-Planet] Error: {0}",
            "covers_err": "❌ [Covers] Anime-Planet: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        path = urlparse(url).path if "://" in url else url
        m = _SLUG.match(path if path.startswith("/") else f"/manga/{path}")
        if m and m.group(1) not in {"all", "tags", "recommendations", "read-online"}:
            return m.group(1)
        if re.fullmatch(r"[a-z0-9\-]+", url.strip(), re.I):
            return url.strip()
        return None

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
                cand = self._parse_manga(session, f"{_BASE}/manga/{slug}")
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(session, cleaned)
            qcf = cleaned.casefold()
            # Tri alpha du site met Boruto avant Naruto — prioriser titre exact / préfixe
            hits.sort(
                key=lambda h: (
                    0 if (h.get("title") or "").casefold() == qcf else 1,
                    0 if (h.get("title") or "").casefold().startswith(qcf) else 1,
                    len(h.get("title") or ""),
                )
            )
            best, best_score = None, -1.0
            for hit in hits[:8]:
                cand = self._parse_manga(session, hit["url"])
                if not cand:
                    # fallback léger depuis la carte
                    cand = {
                        "title": hit["title"],
                        "cover_url": hit.get("cover"),
                        "url": hit["url"],
                        "links": [hit["url"]],
                        "format": "manga",
                        "genres": ["Manga"],
                        "tags": [],
                        "staff": [],
                        "summary": "",
                        "alternative_titles": [],
                    }
                score = score_candidate(cand, cleaned, existing_metadata)
                tcf = (cand.get("title") or "").casefold()
                if tcf == qcf:
                    score = min(1.0, score + 0.20)
                elif tcf.startswith(qcf + " ") or tcf.startswith(qcf + ":"):
                    score = min(1.0, score + 0.05)
                elif qcf in tcf and tcf != qcf:
                    # spin-offs « Naruto Gaiden », « Boruto: Naruto… »
                    score = max(0.0, score - 0.08)
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
                if hit.get("cover"):
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": hit["title"],
                            "url": hit["cover"],
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
            f"{_BASE}/manga/all",
            params={"name": terms, "sort": "title", "order": "asc"},
            timeout=25,
        )
        if res.status_code != 200:
            return []
        soup = BeautifulSoup(res.text, "html.parser")
        hits = []
        for card in soup.select(".cardDeck .card"):
            name_el = card.select_one(".cardName")
            a = card.select_one('a[href*="/manga/"]')
            if not name_el or not a:
                continue
            href = a.get("href") or ""
            slug = self.extract_id_from_url(href)
            if not slug:
                continue
            img = card.select_one("img")
            cover = None
            if img:
                cover = img.get("data-src") or img.get("src")
            hits.append(
                {
                    "title": name_el.get_text(" ", strip=True),
                    "url": f"{_BASE}/manga/{slug}",
                    "cover": cover,
                }
            )
            if len(hits) >= 12:
                break
        return hits

    def _parse_manga(self, session, url: str) -> Optional[Dict[str, Any]]:
        res = session.get(url, timeout=25)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        og_title = soup.select_one('meta[property="og:title"]')
        og_desc = soup.select_one('meta[property="og:description"]')
        og_img = soup.select_one('meta[property="og:image"]')
        title = (og_title.get("content") if og_title else None) or (
            soup.h1.get_text(" ", strip=True) if soup.h1 else ""
        )
        if not title:
            return None
        synopsis = soup.select_one(".entrySynopsis")
        summary = (
            synopsis.get_text(" ", strip=True)
            if synopsis
            else ((og_desc.get("content") if og_desc else "") or "")
        )
        genres, tags = [], []
        for a in soup.select('a[href*="/manga/tags/"]'):
            label = a.get_text(" ", strip=True)
            if not label:
                continue
            # premiers = genres, suivants = tags
            if len(genres) < get_max_genres():
                genres.append(label)
            else:
                tags.append(label)
        staff = []
        for a in soup.select('a[href*="/people/"]'):
            text = a.get_text(" ", strip=True)
            role = "Story"
            name = text
            low = text.casefold()
            if "artist" in low:
                role = "Art"
                name = re.sub(r"\s*Artist\s*$", "", text, flags=re.I).strip()
            elif "author" in low:
                role = "Story"
                name = re.sub(r"\s*Author\s*$", "", text, flags=re.I).strip()
            else:
                continue
            if name:
                staff.append({"role": role, "node": {"name": {"full": name}}})
        year = None
        y = soup.select_one(".iconYear")
        if y:
            m = _YEAR.search(y.get_text(" ", strip=True))
            if m:
                year = int(m.group(1))
        status = None
        st = soup.select_one(".iconStatus")
        if st:
            t = st.get_text(" ", strip=True).casefold()
            if "finished" in t or "completed" in t:
                status = "FINISHED"
            elif "publishing" in t or "ongoing" in t:
                status = "RELEASING"
            elif "hiatus" in t:
                status = "HIATUS"
        out = {
            "title": title.strip(),
            "alternative_titles": [],
            "summary": summary,
            "cover_url": og_img.get("content") if og_img else None,
            "genres": genres[: get_max_genres()] or ["Manga"],
            "tags": tags[: get_max_tags()],
            "year": year,
            "staff": staff[:8],
            "format": "manga",
            "url": url,
            "links": [url],
        }
        if status:
            out["status"] = status
        return out
