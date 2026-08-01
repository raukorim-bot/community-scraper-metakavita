"""League of Comic Geeks — comics (API officielle, clé requise).

Clé MetaKavita LOCG_API_KEY au format :
  client_id:client_secret
(comme les apps Himon / clients API LoCG).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from config_manager import get_max_genres, get_max_tags, load_config
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_API = "https://leagueofcomicgeeks.com/api"
_TOKEN_CACHE: Dict[str, Any] = {"token": None, "exp": 0.0, "key": None}


class LocgScraper(BaseScraper):
    id = "LOCG"
    display_name = "League of Comic Geeks"
    supported_types = {"Comic"}
    rate_limit = 1.0
    proxy_domains = [
        "leagueofcomicgeeks.com",
        "www.leagueofcomicgeeks.com",
        "comicgeeks.app",
    ]
    has_direct_id_support = True
    needs_api_key = True
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [LoCG] Recherche pour '{0}'…",
            "direct_id": "🎯 [LoCG] series_id={0}",
            "no_match": "⚠️ [LoCG] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [LoCG] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [LoCG] Erreur : {0}",
            "covers_err": "❌ [Covers] LoCG : {0}",
            "nokey": "⚠️ [LoCG] Clé requise : client_id:client_secret dans LOCG_API_KEY",
        },
        "en": {
            "search_title": "🔍 [LoCG] Searching for '{0}'…",
            "direct_id": "🎯 [LoCG] series_id={0}",
            "no_match": "⚠️ [LoCG] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [LoCG] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [LoCG] Error: {0}",
            "covers_err": "❌ [Covers] LoCG: {0}",
            "nokey": "⚠️ [LoCG] API key required: client_id:client_secret in LOCG_API_KEY",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        if url.strip().isdigit():
            return url.strip()
        path = urlparse(url).path if "://" in url else url
        parts = [p for p in path.split("/") if p]
        for i, p in enumerate(parts):
            if p in {"series", "comic"} and i + 1 < len(parts) and parts[i + 1].isdigit():
                return parts[i + 1]
            if p.isdigit() and i > 0 and parts[i - 1] in {"series", "comics"}:
                return p
        return None

    def _creds(self) -> Optional[tuple]:
        raw = (load_config().get("LOCG_API_KEY") or "").strip()
        if not raw or ":" not in raw:
            return None
        cid, secret = raw.split(":", 1)
        cid, secret = cid.strip(), secret.strip()
        if not cid or not secret:
            return None
        return cid, secret

    def _auth_headers(self) -> Optional[Dict[str, str]]:
        creds = self._creds()
        if not creds:
            logging.warning(self.t("nokey"))
            return None
        cid, secret = creds
        cache_key = f"{cid}:{secret}"
        now = time.time()
        if (
            _TOKEN_CACHE.get("token")
            and _TOKEN_CACHE.get("key") == cache_key
            and now < float(_TOKEN_CACHE.get("exp") or 0)
        ):
            token = _TOKEN_CACHE["token"]
            return {
                "X-API-CLIENT": cid,
                "X-API-KEY": secret,
                "Authorization": f"Bearer {token}",
            }

        res = requests.post(
            f"{_API}/authorize",
            headers={"X-API-CLIENT": cid, "X-API-KEY": secret},
            timeout=25,
        )
        if res.status_code != 200:
            # fallback: headers client/secret seuls (certains endpoints)
            if res.status_code in (404, 405):
                return {"X-API-CLIENT": cid, "X-API-KEY": secret}
            logging.error(self.t("err").format(f"authorize {res.status_code}"))
            return {"X-API-CLIENT": cid, "X-API-KEY": secret}

        data = res.json() if res.content else {}
        token = data.get("access_token") or data.get("token") or data.get("api_key")
        if not token:
            return {"X-API-CLIENT": cid, "X-API-KEY": secret}
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["key"] = cache_key
        _TOKEN_CACHE["exp"] = now + float(data.get("expires_in") or 3500)
        return {
            "X-API-CLIENT": cid,
            "X-API-KEY": secret,
            "Authorization": f"Bearer {token}",
        }

    def fetch(
        self,
        query: str,
        library_type: str = "Comic",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        headers = self._auth_headers()
        if not headers:
            return None
        try:
            if is_id:
                sid = self.extract_id_from_url(query)
                if not sid:
                    return None
                logging.info(self.t("direct_id").format(sid))
                cand = self._series(headers, sid)
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(headers, cleaned)
            best, best_score = None, -1.0
            for hit in hits[:6]:
                cand = self._series(headers, str(hit["id"])) if hit.get("id") else None
                if not cand:
                    cand = self._hit_to_cand(hit)
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

    def fetch_covers(self, query: str, library_type: str = "Comic") -> List[Dict[str, str]]:
        covers = []
        headers = self._auth_headers()
        if not headers:
            return covers
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        try:
            for hit in self._search(headers, cleaned)[:5]:
                url = hit.get("cover") or hit.get("image") or hit.get("cover_url")
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

    def _search(self, headers: Dict[str, str], terms: str) -> List[dict]:
        for path in ("/search/series", "/comic/search", "/search"):
            try:
                res = requests.get(
                    f"{_API}{path}",
                    headers=headers,
                    params={"query": terms, "q": terms, "name": terms},
                    timeout=25,
                )
                if res.status_code != 200:
                    continue
                data = res.json()
                items = (
                    data
                    if isinstance(data, list)
                    else data.get("results")
                    or data.get("series")
                    or data.get("data")
                    or []
                )
                out = []
                for it in items[:15]:
                    if not isinstance(it, dict):
                        continue
                    sid = it.get("id") or it.get("series_id")
                    title = it.get("title") or it.get("name")
                    if not title:
                        continue
                    out.append(
                        {
                            "id": sid,
                            "title": title,
                            "cover": it.get("cover")
                            or it.get("image")
                            or (it.get("covers") or {}).get("medium"),
                            "url": it.get("url")
                            or (
                                f"https://leagueofcomicgeeks.com/comic/series/{sid}"
                                if sid
                                else None
                            ),
                        }
                    )
                if out:
                    return out
            except Exception:
                continue
        return []

    def _series(self, headers: Dict[str, str], sid: str) -> Optional[Dict[str, Any]]:
        for path in (f"/series/{sid}", f"/comic/series/{sid}", f"/comics/series/{sid}"):
            try:
                res = requests.get(f"{_API}{path}", headers=headers, timeout=25)
                if res.status_code != 200:
                    continue
                data = res.json()
                if isinstance(data, dict) and data.get("data"):
                    data = data["data"]
                if not isinstance(data, dict):
                    continue
                return self._hit_to_cand(
                    {
                        "id": sid,
                        "title": data.get("title") or data.get("name"),
                        "cover": data.get("cover")
                        or data.get("image")
                        or (data.get("covers") or {}).get("large"),
                        "url": data.get("url")
                        or f"https://leagueofcomicgeeks.com/comic/series/{sid}",
                        "description": data.get("description")
                        or data.get("summary")
                        or "",
                        "year": data.get("year") or data.get("start_year"),
                        "publisher": data.get("publisher"),
                    }
                )
            except Exception:
                continue
        return None

    def _hit_to_cand(self, hit: dict) -> Optional[Dict[str, Any]]:
        title = hit.get("title")
        if not title:
            return None
        url = hit.get("url") or (
            f"https://leagueofcomicgeeks.com/comic/series/{hit['id']}"
            if hit.get("id")
            else None
        )
        staff = []
        pub = hit.get("publisher")
        if isinstance(pub, dict):
            pub = pub.get("name")
        if pub:
            staff.append({"role": "Publisher", "node": {"name": {"full": str(pub)}}})
        return {
            "title": title,
            "alternative_titles": [],
            "summary": hit.get("description") or "",
            "cover_url": hit.get("cover"),
            "genres": ["Comic"][: get_max_genres()],
            "tags": [],
            "year": hit.get("year"),
            "staff": staff,
            "format": "comic",
            "url": url,
            "links": [url] if url else [],
        }
