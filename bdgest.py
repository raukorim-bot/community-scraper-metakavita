"""BDgest / Bédéthèque — métadonnées BD FR via bedetheque.com (HTML).

La recherche bdgest.com/search est morte (404). On utilise
https://www.bedetheque.com/search/albums?RechSerie=… puis les pages
serie-N-BD-Slug.html dérivées des albums.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
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

_BASE = "https://www.bedetheque.com"
_SERIES = re.compile(r"serie-(\d+)-BD-([^/?#]+)\.html", re.I)
_ALBUM = re.compile(r"BD-[^/]+-(\d+)\.html", re.I)
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


class BdgestScraper(BaseScraper):
    id = "BDGEST"
    display_name = "BDgest / Bédéthèque"
    supported_types = {"Comic"}
    rate_limit = 3.0  # HTML bedetheque.com — anti-ban IP
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
            "search_title": "🔍 [Bédéthèque] Recherche pour '{0}'…",
            "direct_id": "🎯 [Bédéthèque] serie={0}",
            "no_match": "⚠️ [Bédéthèque] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Bédéthèque] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Bédéthèque] Erreur : {0}",
            "covers_err": "❌ [Covers] Bédéthèque : {0}",
        },
        "en": {
            "search_title": "🔍 [Bédéthèque] Searching for '{0}'…",
            "direct_id": "🎯 [Bédéthèque] series={0}",
            "no_match": "⚠️ [Bédéthèque] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Bédéthèque] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Bédéthèque] Error: {0}",
            "covers_err": "❌ [Covers] Bédéthèque: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        if url.strip().isdigit():
            return url.strip()
        m = _SERIES.search(url)
        if m:
            return m.group(1)
        path = urlparse(url).path if "://" in url else url
        m = _SERIES.search(path)
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Comic",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        session.headers.update(
            {
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
                "Referer": f"{_BASE}/",
            }
        )
        try:
            if is_id:
                sid = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(sid))
                urls = []
                if "://" in query:
                    urls.append(query)
                urls.append(f"{_BASE}/serie-{sid}-BD-.html")
                # sans slug exact : chercher via albums puis série
                if sid.isdigit():
                    # tenter de trouver une page série via search id dans hits
                    pass
                for url in urls:
                    cand = self._parse_series(session, url)
                    if cand:
                        return attach_match_score(cand, 1.0)
                # fallback : search by numeric id in serie links after a broad fetch
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
                    score = min(1.0, score + 0.15)
                # Pénaliser albums "Tome N" vs série
                if re.search(r"\b#?\d+\b", cand.get("title") or ""):
                    score = max(0.0, score - 0.05)
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
        # Mêmes headers que fetch() — sans Referer/langue, search/albums renvoie souvent
        # le formulaire vide (0 hit) et le picker de covers reste silencieux.
        session.headers.update(
            {
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
                "Referer": f"{_BASE}/",
            }
        )
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
        """Search albums by series name, group by serie-N-BD-Slug pages."""
        # Warmup cookies / csrf
        try:
            session.get(_BASE + "/", timeout=20)
        except Exception:
            pass

        res = session.get(
            f"{_BASE}/search/albums",
            params={"RechSerie": terms},
            timeout=40,
        )
        if res.status_code != 200 or len(res.text) < 1000:
            return []

        soup = BeautifulSoup(res.text, "html.parser")
        hits, seen = [], set()
        qcf = terms.casefold()

        def _slug_title(slug: str) -> str:
            return slug.replace("-", " ").replace("_", " ").strip()

        # Direct series links only (serie-123-BD-Slug.html) — pas « 5eme-serie » dans un album
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            m = _SERIES.search(href)
            if not m:
                continue
            sid = m.group(1)
            if sid in seen:
                continue
            title = a.get_text(" ", strip=True)
            if not title or title.casefold() in {"la série", "série", "series"}:
                title = _slug_title(m.group(2))
            if not title or len(title) < 2:
                continue
            seen.add(sid)
            full = urljoin(_BASE + "/", href)
            hits.append({"title": title, "url": full.split("?")[0], "id": sid})
            if len(hits) >= 12:
                return hits

        # Albums candidats — scorer pour éviter DOC / hors-série / coloriage
        album_cands: List[Tuple[float, str, str]] = []
        for a in soup.select("a[href*='BD-']"):
            href = a.get("href") or ""
            if _SERIES.search(href):
                continue
            if not re.search(r"BD-.+\d+\.html", href, re.I):
                continue
            full = urljoin(_BASE + "/", href).split("?")[0]
            label = a.get_text(" ", strip=True)
            if not label:
                continue
            lcf = label.casefold()
            hcf = href.casefold()
            score = 0.0
            if lcf.startswith(qcf + " #") or lcf.startswith(qcf + " tome"):
                score += 5.0
            elif lcf.startswith(qcf):
                score += 2.0
            if f"bd-{qcf.replace(' ', '-')}-tome-" in hcf.replace("é", "e").replace("è", "e"):
                score += 4.0
            if "tome-" in hcf:
                score += 1.5
            # Bruit
            for bad in (
                "doc-",
                "journal-",
                "colorier",
                "hors-serie",
                "hors série",
                "divers",
                "parabd",
                "archives",
            ):
                if bad in hcf or bad in lcf:
                    score -= 5.0
            album_cands.append((score, full, label))

        album_cands.sort(key=lambda x: (-x[0], x[2]))
        albums = []
        for sc, full, _label in album_cands:
            if full in albums:
                continue
            if sc < 0:
                continue
            albums.append(full)
            if len(albums) >= 6:
                break

        for album_url in albums:
            try:
                ar = session.get(album_url, timeout=25)
            except Exception:
                continue
            if ar.status_code != 200:
                continue
            asoup = BeautifulSoup(ar.text, "html.parser")
            for a in asoup.select("a[href]"):
                href = a.get("href") or ""
                m = _SERIES.search(href)
                if not m:
                    continue
                sid = m.group(1)
                if sid in seen:
                    continue
                title = a.get_text(" ", strip=True)
                if not title or title.casefold() in {"la série", "série"}:
                    title = _slug_title(m.group(2))
                # Préférer la série dont le titre colle à la requête
                if qcf not in title.casefold() and qcf not in m.group(2).casefold().replace("-", " "):
                    continue
                seen.add(sid)
                hits.append(
                    {
                        "title": title,
                        "url": urljoin(_BASE + "/", href).split("?")[0],
                        "id": sid,
                    }
                )
                break
            if len(hits) >= 8:
                break

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
            # lien série dans la page
            for a in soup.select('a[href*="serie-"]'):
                t = a.get_text(" ", strip=True)
                if t and t.casefold() not in {"la série", "série"}:
                    title = t
                    break
        if not title:
            return None
        title = re.sub(
            r"\s*[-|]\s*(BDgest|Bédéthèque|Bedetheque).*$", "", title, flags=re.I
        ).strip()
        title = re.sub(
            r"\s*[-–—]\s*BD,?\s*informations.*$", "", title, flags=re.I
        ).strip()
        title = re.sub(r"\s*,\s*cotes\s*$", "", title, flags=re.I).strip()
        # "Astérix -1- Astérix le Gaulois" → garder série si on est sur album
        if re.search(r"\s-\d+-\s", title):
            title = re.split(r"\s-\d+-\s", title, maxsplit=1)[0].strip()

        authors = []
        for sel in (
            ".auteur a",
            ".infos a[href*='auteur']",
            "a[href*='/auteur']",
            "a[href*='Auteur-']",
        ):
            for el in soup.select(sel):
                n = el.get_text(" ", strip=True)
                if n and n not in authors and len(n) < 60:
                    authors.append(n)
        staff = [
            {"role": "Story & Art", "node": {"name": {"full": n}}} for n in authors[:4]
        ]
        year = None
        # Bandeau série : "Astérix Humour … 1961-2025"
        bandeau = soup.select_one(".bandeau-info.serie") or soup.select_one(".bandeau-info")
        if bandeau:
            bt = bandeau.get_text(" ", strip=True)
            m = re.search(r"(19\d{2}|20\d{2})\s*[-–—]\s*(?:\d{4}|…|\.{2,})?", bt)
            if m:
                year = int(m.group(1))
        if year is None:
            m = _YEAR.search(soup.get_text(" ", strip=True)[:2500])
            if m:
                y = int(m.group(1))
                if 1900 <= y <= 2030:
                    year = y

        genres = ["Comic"]
        if bandeau:
            # "Astérix Humour Série en cours Europe …"
            parts = bandeau.get_text(" ", strip=True).split()
            skip = {title.casefold(), "série", "serie", "en", "cours", "europe", "albums", "français", "francais"}
            for p in parts[1:6]:
                if p.casefold() in skip or re.fullmatch(r"\d{4}(-\d{4})?", p):
                    continue
                if p[0].isupper() and len(p) > 2:
                    genres = [p]
                    break

        # Prefer series URL if we landed on an album
        series_url = url.split("?")[0]
        for a in soup.select('a[href*="serie-"]'):
            href = a.get("href") or ""
            if _SERIES.search(href):
                series_url = urljoin(_BASE + "/", href).split("?")[0]
                break

        return {
            "title": title,
            "alternative_titles": [],
            "summary": (og_desc.get("content") if og_desc else "") or "",
            "cover_url": og_img.get("content") if og_img else None,
            "genres": genres[: get_max_genres()],
            "tags": [],
            "year": year,
            "staff": staff,
            "format": "comic",
            "url": series_url,
            "links": [series_url],
        }
