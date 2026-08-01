"""Manga-Sanctuary — métadonnées manga FR (HTML)."""
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

_BASE = "https://www.manga-sanctuary.com"
_MANGA = re.compile(r"^/bdd/manga/(\d+)(?:-[^/?#]*)?/?$", re.I)
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


class MangaSanctuaryScraper(BaseScraper):
    id = "MANGASANCTUARY"
    display_name = "Manga-Sanctuary"
    supported_types = {"Manga"}
    rate_limit = 1.5
    proxy_domains = ["manga-sanctuary.com", "www.manga-sanctuary.com"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [Manga-Sanctuary] Recherche pour '{0}'…",
            "direct_id": "🎯 [Manga-Sanctuary] id={0}",
            "no_match": "⚠️ [Manga-Sanctuary] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Manga-Sanctuary] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Manga-Sanctuary] Erreur : {0}",
            "covers_err": "❌ [Covers] Manga-Sanctuary : {0}",
        },
        "en": {
            "search_title": "🔍 [Manga-Sanctuary] Searching for '{0}'…",
            "direct_id": "🎯 [Manga-Sanctuary] id={0}",
            "no_match": "⚠️ [Manga-Sanctuary] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Manga-Sanctuary] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Manga-Sanctuary] Error: {0}",
            "covers_err": "❌ [Covers] Manga-Sanctuary: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        if url.strip().isdigit():
            return url.strip()
        path = urlparse(url).path if "://" in url else url
        m = _MANGA.match(path if path.startswith("/") else f"/bdd/manga/{path}")
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Manga",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        session.headers.update(
            {"Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5", "Referer": f"{_BASE}/"}
        )
        try:
            if is_id:
                mid = self.extract_id_from_url(query)
                if not mid:
                    return None
                logging.info(self.t("direct_id").format(mid))
                url = query if "manga-sanctuary.com" in query else f"{_BASE}/bdd/manga/{mid}/"
                cand = self._parse_manga(session, url)
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(session, cleaned)
            best, best_score = None, -1.0
            for hit in hits[:8]:
                cand = self._parse_manga(session, hit["url"])
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

    def fetch_covers(self, query: str, library_type: str = "Manga") -> List[Dict[str, str]]:
        covers = []
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        session = requests.Session(impersonate="chrome110")
        try:
            for hit in self._search(session, cleaned)[:5]:
                cand = self._parse_manga(session, hit["url"])
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
        # La page /recherche.php est JS / 0 résultat en GET.
        # Autocomplete XHR : /include/ajax_rechercher_mots.php?chaine=
        res = session.post(
            f"{_BASE}/include/ajax_rechercher_mots.php",
            data={"chaine": terms},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"{_BASE}/",
            },
            timeout=25,
        )
        if res.status_code != 200 or not res.text.strip():
            return []
        soup = BeautifulSoup(res.text, "html.parser")
        hits, seen = [], set()
        for a in soup.select('a[href*="/bdd/manga/"]'):
            href = a.get("href") or ""
            mid = self.extract_id_from_url(href)
            if not mid or mid in seen:
                continue
            title = a.get_text(" ", strip=True)
            # "death note (Manga)" → "death note"
            title = re.sub(r"\s*\((?:Manga|Manhwa|Manhua)\)\s*$", "", title, flags=re.I).strip()
            if not title or len(title) < 2:
                continue
            seen.add(mid)
            hits.append({"title": title, "url": urljoin(_BASE, href)})
            if len(hits) >= 15:
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
        title = (og_title.get("content") if og_title else "").strip()
        if not title and soup.h1:
            title = soup.h1.get_text(" ", strip=True)
        if not title:
            return None
        # Nettoyage suffixe site
        title = re.sub(r"\s*[-|]\s*Manga.?Sanctuary.*$", "", title, flags=re.I).strip()

        genres, tags = [], []
        for a in soup.select('a[href*="genre"], a[href*="theme"], .genres a, .tags a'):
            label = a.get_text(" ", strip=True)
            if not label or len(label) > 40:
                continue
            if len(genres) < get_max_genres():
                genres.append(label)
            else:
                tags.append(label)

        staff = []
        for label, role in (("Auteur", "Story"), ("Scénariste", "Story"), ("Dessinateur", "Art")):
            for el in soup.find_all(string=re.compile(label, re.I)):
                parent = el.parent
                if not parent:
                    continue
                link = parent.find_next("a")
                if link:
                    name = link.get_text(" ", strip=True)
                    if name:
                        staff.append({"role": role, "node": {"name": {"full": name}}})

        year = None
        text = soup.get_text(" ", strip=True)
        for m in _YEAR.finditer(text[:2000]):
            y = int(m.group(1))
            if 1950 <= y <= 2030:
                year = y
                break

        mid = self.extract_id_from_url(url)
        page_url = url.split("?")[0]
        if mid and "/bdd/manga/" not in page_url:
            page_url = f"{_BASE}/bdd/manga/{mid}/"

        return {
            "title": title,
            "alternative_titles": [],
            "summary": (og_desc.get("content") if og_desc else "") or "",
            "cover_url": og_img.get("content") if og_img else None,
            "genres": (genres or ["Manga"])[: get_max_genres()],
            "tags": tags[: get_max_tags()],
            "year": year,
            "staff": staff[:8],
            "format": "manga",
            "url": page_url,
            "links": [page_url],
        }
