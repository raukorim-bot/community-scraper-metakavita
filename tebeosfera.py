"""Tebeosfera — comics / tebeos ES (HTML, best-effort)."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

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

_BASE = "https://www.tebeosfera.com"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


def _abs(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return urljoin(_BASE, url.split("#", 1)[0])


class TebeosferaScraper(BaseScraper):
    id = "TEBEOSFERA"
    display_name = "Tebeosfera"
    supported_types = {"Comic"}
    rate_limit = 3.0  # HTML ES — anti-ban IP
    proxy_domains = ["tebeosfera.com", "www.tebeosfera.com"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [Tebeosfera] Recherche pour '{0}'…",
            "direct_id": "🎯 [Tebeosfera] path={0}",
            "no_match": "⚠️ [Tebeosfera] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Tebeosfera] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Tebeosfera] Erreur : {0}",
            "covers_err": "❌ [Covers] Tebeosfera : {0}",
        },
        "en": {
            "search_title": "🔍 [Tebeosfera] Searching for '{0}'…",
            "direct_id": "🎯 [Tebeosfera] path={0}",
            "no_match": "⚠️ [Tebeosfera] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Tebeosfera] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Tebeosfera] Error: {0}",
            "covers_err": "❌ [Covers] Tebeosfera: {0}",
        },
    }

    def __init__(self) -> None:
        self._session = requests.Session(impersonate="chrome110")
        self._session.headers.update(
            {
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
                "Referer": f"{_BASE}/",
            }
        )

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = url.strip()
        if raw.startswith("/") and "tebeosfera" not in raw:
            return raw
        path = urlparse(raw).path if "://" in raw else raw
        if "/obras/" in path or "/numeros/" in path or "/autores/" in path:
            return path
        return None

    def fetch(
        self,
        query: str,
        library_type: str = "Comic",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            if is_id:
                path = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(path))
                cand = self._parse_detail(_abs(path) or f"{_BASE}{path}")
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(cleaned)
            best, best_score = None, -1.0
            for hit in hits[:8]:
                seed = self._hit_to_cand(hit)
                if not seed:
                    continue
                score = score_candidate(seed, cleaned, existing_metadata)
                detail = None
                if score >= get_match_accept_threshold() - 0.15 and hit.get("url"):
                    detail = self._parse_detail(hit["url"])
                cand = detail or seed
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

    def fetch_covers(self, query: str, library_type: str = "Comic") -> List[Dict[str, str]]:
        covers: List[Dict[str, str]] = []
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        try:
            for hit in self._search(cleaned)[:6]:
                url = hit.get("cover")
                if url:
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": hit.get("title") or cleaned,
                            "url": url,
                        }
                    )
        except Exception as e:
            logging.error(self.t("covers_err").format(e))
        return covers

    def _search(self, terms: str) -> List[dict]:
        # Plusieurs formes d’URL de recherche historiques / actuelles
        candidates = [
            f"{_BASE}/buscador.php?buscar={quote_plus(terms)}",
            f"{_BASE}/busqueda/?q={quote_plus(terms)}",
            f"{_BASE}/?s={quote_plus(terms)}",
            f"{_BASE}/obras/?q={quote_plus(terms)}",
        ]
        out: List[dict] = []
        seen = set()
        for url in candidates:
            res = self._session.get(url, timeout=25)
            if res.status_code != 200 or len(res.text) < 500:
                continue
            if "just a moment" in res.text.casefold():
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.select("a[href*='/obras/'], a[href*='/numeros/']"):
                href = _abs(a.get("href"))
                if not href or href in seen:
                    continue
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 2:
                    continue
                seen.add(href)
                img = a.find("img")
                cover = None
                if img:
                    cover = _abs(img.get("data-src") or img.get("src"))
                out.append({"title": title, "url": href, "cover": cover})
            if out:
                break
        return out

    def _hit_to_cand(self, hit: dict) -> Optional[Dict[str, Any]]:
        title = hit.get("title")
        if not title:
            return None
        url = hit.get("url")
        return {
            "title": title,
            "alternative_titles": [],
            "summary": "",
            "cover_url": hit.get("cover"),
            "genres": ["Comic"][: get_max_genres()],
            "tags": [],
            "year": None,
            "staff": [],
            "format": "comic",
            "url": url,
            "links": [url] if url else [],
        }

    def _parse_detail(self, url: str) -> Optional[Dict[str, Any]]:
        res = self._session.get(url, timeout=25)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        title = None
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True).split("|")[0].strip()
        if not title:
            return None
        summary = ""
        for sel in (".sinopsis", ".resumen", ".descripcion", "meta[name='description']"):
            el = soup.select_one(sel)
            if not el:
                continue
            summary = (
                el.get("content") if el.name == "meta" else el.get_text(" ", strip=True)
            ) or ""
            if summary:
                break
        year = None
        blob = soup.get_text(" ", strip=True)[:2000]
        m = _YEAR.search(blob)
        if m:
            year = int(m.group(1))
        cover = None
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            cover = _abs(og["content"])
        if not cover:
            img = soup.select_one("article img, .portada img, .cover img, img")
            if img:
                cover = _abs(img.get("data-src") or img.get("src"))
        staff = []
        for sel in (".autor a", ".autores a", "a[href*='/autores/']"):
            for a in soup.select(sel)[:5]:
                name = a.get_text(" ", strip=True)
                if name:
                    staff.append({"role": "Story", "node": {"name": {"full": name}}})
            if staff:
                break
        return {
            "title": title,
            "alternative_titles": [],
            "summary": summary,
            "cover_url": cover,
            "genres": ["Comic"][: get_max_genres()],
            "tags": [],
            "year": year,
            "staff": staff,
            "format": "comic",
            "url": url,
            "links": [url],
        }
