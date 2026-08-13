"""Grand Comics Database (comics.org) — métadonnées comics via API JSON publique.

Le site HTML est derrière Cloudflare, mais `/api/` renvoie du JSON sans challenge.
Auth optionnelle (Basic) via `GCD_API_KEY` = `user:password` pour des quotas plus élevés.
Doc : https://github.com/GrandComicsDatabase/gcd-django/wiki/API
"""
from __future__ import annotations

import logging
import re
import threading
import time
from base64 import b64encode
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags, load_config
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    extract_year_from_title,
    get_match_accept_threshold,
    score_candidate,
)

_API = "https://www.comics.org/api"
_SITE = "https://www.comics.org"
_SERIES_RE = re.compile(r"/series/(\d+)/?", re.I)
_ISSUE_RE = re.compile(r"/issue/(\d+)/?", re.I)
_CREDIT_NONE = re.compile(r"^(none|\?+|n/?a)$", re.I)

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

# Éditions / collectes à pénaliser si absentes de la requête
_EDITION_NOISE = (
    "absolute",
    "annotated",
    "omnibus",
    "deluxe",
    "library edition",
    "dollar comics",
    "millennium edition",
    "essential vertigo",
    "dce essentials",
    "hardcover",
    "tpb",
    "compendium",
    "showcase",
    "archives",
    "special edition",
    "director's cut",
    "facsimile",
)


def _norm_cover(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return re.sub(r"(https?://[^/]+)//+", r"\1/", url.strip())


def _split_credits(raw: Optional[str]) -> List[str]:
    if not raw or not isinstance(raw, str):
        return []
    names = []
    for part in re.split(r"\s*;\s*|\s+and\s+|\s*&\s*|\s*/\s*", raw):
        name = re.sub(r"\s*\([^)]*\)\s*", " ", part).strip()
        name = re.sub(r"\s*\[.*?\]\s*", " ", name).strip()
        if not name or _CREDIT_NONE.match(name):
            continue
        if name not in names:
            names.append(name)
    return names


class GcdScraper(BaseScraper):
    id = "GCD"
    display_name = "Grand Comics Database"
    # 1.1.0 : `_get_json`, point de passage unique des appels API, applique
    # désormais la cadence — elle ne l'était qu'une fois par `fetch()`.
    version = "1.1.0"
    supported_types = {"Comic"}
    rate_limit = 2.0
    proxy_domains = [
        "comics.org",
        "www.comics.org",
        "files1.comics.org",
        "files2.comics.org",
        "files.comics.org",
    ]
    has_direct_id_support = True
    needs_api_key = False  # optionnel : user:password → GCD_API_KEY
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [GCD] Recherche pour '{0}'…",
            "direct_id": "🎯 [GCD] series_id={0}",
            "no_match": "⚠️ [GCD] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [GCD] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [GCD] Erreur : {0}",
            "covers_err": "❌ [Covers] GCD : {0}",
            "rate": "⚠️ [GCD] Rate-limit API (429) — réessayez plus tard",
        },
        "en": {
            "search_title": "🔍 [GCD] Searching for '{0}'…",
            "direct_id": "🎯 [GCD] series_id={0}",
            "no_match": "⚠️ [GCD] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [GCD] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [GCD] Error: {0}",
            "covers_err": "❌ [Covers] GCD: {0}",
            "rate": "⚠️ [GCD] API rate-limited (429) — try again later",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        if url.strip().isdigit():
            return url.strip()
        m = _SERIES_RE.search(url)
        if m:
            return m.group(1)
        m = _ISSUE_RE.search(url)
        if m:
            return f"issue:{m.group(1)}"
        path = urlparse(url).path if "://" in url else url
        m = _SERIES_RE.search(path)
        return m.group(1) if m else None

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "MetaKavita-GCD/1.0 (community-scraper; +https://github.com/raukorim-bot/community-scraper-metakavita)",
        }
        key = ""
        try:
            key = (load_config().get("GCD_API_KEY") or "").strip()
        except Exception:
            key = ""
        if key and ":" in key:
            user, _, password = key.partition(":")
            if user and password:
                token = b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
                headers["Authorization"] = f"Basic {token}"
        return headers

    def fetch(
        self,
        query: str,
        library_type: str = "Comic",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session(impersonate="chrome110")
        headers = self._headers()
        try:
            if is_id:
                raw = self.extract_id_from_url(query) or query.strip()
                if raw.startswith("issue:"):
                    issue = self._get_json(session, headers, f"{_API}/issue/{raw[6:]}/")
                    if not issue or not issue.get("series"):
                        return None
                    sid = self.extract_id_from_url(issue["series"])
                    if not sid:
                        return None
                    logging.info(self.t("direct_id").format(sid))
                    cand = self._series_to_candidate(
                        session, headers, sid, issue_for_cover=issue
                    )
                    return attach_match_score(cand, 1.0) if cand else None

                logging.info(self.t("direct_id").format(raw))
                cand = self._series_to_candidate(session, headers, raw)
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None

            year_hint = None
            if existing_metadata and existing_metadata.get("year") is not None:
                try:
                    year_hint = int(existing_metadata["year"])
                except (TypeError, ValueError):
                    year_hint = None
            if year_hint is None:
                year_hint = extract_year_from_title(query)

            logging.info(self.t("search_title").format(cleaned))
            hits = self._search_series(session, headers, cleaned, year_hint=year_hint)
            if hits is None:
                return None
            if not hits:
                logging.warning(self.t("no_match").format(cleaned, 0))
                return None

            ranked: List[Tuple[float, dict]] = []
            for hit in hits:
                prelim = self._hit_prelim(hit)
                if not prelim:
                    continue
                score = score_candidate(prelim, cleaned, existing_metadata)
                score = self._adjust_score(score, hit, cleaned, year_hint)
                ranked.append((score, hit))
            ranked.sort(key=lambda x: x[0], reverse=True)

            best, best_score = None, -1.0
            for prelim_score, hit in ranked[:4]:
                sid = self.extract_id_from_url(hit.get("api_url") or "")
                if not sid:
                    continue
                cand = self._series_to_candidate(session, headers, sid, list_hit=hit)
                if not cand:
                    continue
                score = score_candidate(cand, cleaned, existing_metadata)
                score = self._adjust_score(score, hit, cleaned, year_hint)
                # garder le max entre pré-score et détail
                score = max(score, prelim_score)
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
        covers: List[Dict[str, str]] = []
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        session = requests.Session(impersonate="chrome110")
        headers = self._headers()
        try:
            year_hint = extract_year_from_title(query)
            hits = self._search_series(session, headers, cleaned, year_hint=year_hint) or []
            for hit in hits[:5]:
                sid = self.extract_id_from_url(hit.get("api_url") or "")
                if not sid:
                    continue
                cover = self._first_cover(session, headers, hit)
                if cover:
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": hit.get("name") or cleaned,
                            "url": cover,
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

    # ------------------------------------------------------------------ API

    def _get_json(
        self, session, headers: Dict[str, str], url: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        res = _throttled_get(self, session, url, headers=headers, params=params, timeout=30)
        if res.status_code == 429:
            logging.warning(self.t("rate"))
            return None
        if res.status_code != 200:
            return None
        try:
            data = res.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _search_series(
        self,
        session,
        headers: Dict[str, str],
        terms: str,
        year_hint: Optional[int] = None,
    ) -> Optional[List[dict]]:
        """Recherche name-contains + ciblage des titres exacts (tri alpha API)."""
        encoded = quote(terms, safe="")
        hits: List[dict] = []
        seen: set = set()

        def _add(items: List[dict]) -> None:
            for it in items:
                if not isinstance(it, dict):
                    continue
                key = it.get("api_url") or it.get("name")
                if not key or key in seen:
                    continue
                seen.add(key)
                hits.append(it)

        if year_hint:
            data = self._get_json(
                session,
                headers,
                f"{_API}/series/name/{encoded}/year/{int(year_hint)}/",
            )
            if data is None and year_hint:
                # 429
                return None
            if data:
                _add(data.get("results") or [])

        # Page 1 contains
        first = self._get_json(
            session, headers, f"{_API}/series/name/{encoded}/", params={"page": 1}
        )
        if first is None:
            return hits or None
        page_results = first.get("results") or []
        _add(page_results)
        count = int(first.get("count") or 0)
        page_size = len(page_results) or 50
        total_pages = max(1, (count + page_size - 1) // page_size) if count else 1

        # Collecter les exact match via recherche dichotomique (noms triés)
        exact = self._collect_exact_name(
            session, headers, encoded, terms.casefold(), total_pages, page_size
        )
        _add(exact)

        # Une 2e page contains si encore peu de matière
        if len(hits) < 8 and first.get("next"):
            page2 = self._get_json(
                session, headers, f"{_API}/series/name/{encoded}/", params={"page": 2}
            )
            if page2:
                _add(page2.get("results") or [])

        return hits

    def _collect_exact_name(
        self,
        session,
        headers: Dict[str, str],
        encoded: str,
        qcf: str,
        total_pages: int,
        page_size: int,
    ) -> List[dict]:
        """Les résultats contains sont triés alpha — dichotomie pour trouver le bloc exact."""
        if total_pages <= 1:
            return []
        _ = page_size  # réservé / clarté

        def page_names(page: int) -> Tuple[Optional[List[dict]], List[str]]:
            data = self._get_json(
                session,
                headers,
                f"{_API}/series/name/{encoded}/",
                params={"page": page},
            )
            if not data:
                return None, []
            results = [r for r in (data.get("results") or []) if isinstance(r, dict)]
            names = [(r.get("name") or "").casefold() for r in results]
            return results, names

        lo, hi = 1, total_pages
        leftmost: Optional[int] = None
        for _ in range(10):
            if lo > hi:
                break
            mid = (lo + hi) // 2
            _results, names = page_names(mid)
            if not names:
                break
            if names[-1] < qcf:
                lo = mid + 1
            elif names[0] > qcf:
                hi = mid - 1
            else:
                leftmost = mid
                hi = mid - 1

        if leftmost is None:
            return []

        exact: List[dict] = []
        for page in range(leftmost, min(total_pages, leftmost + 4) + 1):
            results, names = page_names(page)
            if results is None:
                break
            for r, n in zip(results, names):
                if n == qcf:
                    exact.append(r)
            if names and names[0] > qcf:
                break
        return exact

    def _adjust_score(
        self, score: float, hit: dict, cleaned: str, year_hint: Optional[int]
    ) -> float:
        name = (hit.get("name") or "").casefold()
        q = cleaned.casefold()
        if name == q:
            score = min(1.0, score + 0.18)
        elif name.startswith(q + " ") or name.startswith(q + ":"):
            score = min(1.0, score + 0.06)

        issues = len(hit.get("active_issues") or [])
        if issues >= 50:
            score = min(1.0, score + 0.08)
        elif issues >= 12:
            score = min(1.0, score + 0.04)
        elif issues <= 1:
            score = max(0.0, score - 0.04)

        if hit.get("language") == "en":
            score = min(1.0, score + 0.03)
        if hit.get("country") == "us":
            score = min(1.0, score + 0.02)

        for noise in _EDITION_NOISE:
            if noise in name and noise not in q:
                score = max(0.0, score - 0.12)

        if year_hint and hit.get("year_began") == year_hint:
            score = min(1.0, score + 0.1)
        return score

    def _hit_prelim(self, hit: dict) -> Optional[Dict[str, Any]]:
        title = (hit.get("name") or "").strip()
        if not title:
            return None
        sid = self.extract_id_from_url(hit.get("api_url") or "")
        url = f"{_SITE}/series/{sid}/" if sid else None
        year = hit.get("year_began")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None
        status = "FINISHED" if hit.get("year_ended") else "RELEASING"
        return {
            "title": title,
            "alternative_titles": [],
            "summary": (hit.get("notes") or "") or "",
            "cover_url": None,
            "genres": ["Comic"],
            "tags": [],
            "year": year,
            "staff": [],
            "format": "comic",
            "url": url,
            "links": [url] if url else [],
            "status": status,
        }

    def _series_to_candidate(
        self,
        session,
        headers: Dict[str, str],
        sid: str,
        list_hit: Optional[dict] = None,
        issue_for_cover: Optional[dict] = None,
    ) -> Optional[Dict[str, Any]]:
        detail = self._get_json(session, headers, f"{_API}/series/{sid}/")
        if not detail:
            detail = list_hit
        if not detail:
            return None
        title = (detail.get("name") or "").strip()
        if not title:
            return None

        publisher = None
        pub_url = detail.get("publisher")
        if isinstance(pub_url, str) and pub_url.startswith("http"):
            pub = self._get_json(session, headers, pub_url)
            if pub:
                publisher = pub.get("name")

        cover = _norm_cover((issue_for_cover or {}).get("cover"))
        staff: List[dict] = []
        genres: List[str] = []
        summary = (detail.get("notes") or "").strip()

        first_issue = issue_for_cover
        if not first_issue:
            issues = detail.get("active_issues") or []
            if issues:
                first_issue = self._get_json(session, headers, issues[0])

        if first_issue:
            if not cover:
                cover = _norm_cover(first_issue.get("cover"))
            for story in first_issue.get("story_set") or []:
                if not isinstance(story, dict):
                    continue
                stype = (story.get("type") or "").casefold()
                if stype in {"cover", "in-house column", "promo", "ad", "letters page"}:
                    continue
                for role_key, role in (
                    ("script", "Story"),
                    ("pencils", "Art"),
                    ("inks", "Inks"),
                ):
                    for name in _split_credits(story.get(role_key)):
                        entry = {"role": role, "node": {"name": {"full": name}}}
                        if entry not in staff:
                            staff.append(entry)
                g = (story.get("genre") or "").strip()
                if g:
                    for part in re.split(r"\s*;\s*|\s*,\s*", g):
                        part = part.strip()
                        if part and part not in genres:
                            genres.append(part)
                syn = (story.get("synopsis") or "").strip()
                if syn and (not summary or len(syn) > len(summary)):
                    summary = syn
                if staff and genres:
                    break

        year = detail.get("year_began")
        try:
            year = int(year) if year is not None else None
        except (TypeError, ValueError):
            year = None

        status = "FINISHED" if detail.get("year_ended") else "RELEASING"
        fmt = (detail.get("publishing_format") or "").strip()
        tags = []
        if fmt:
            tags.append(fmt)
        country = detail.get("country")
        language = detail.get("language")
        if country:
            tags.append(f"country:{country}")
        if language:
            tags.append(f"lang:{language}")

        url = f"{_SITE}/series/{sid}/"
        out: Dict[str, Any] = {
            "title": title,
            "alternative_titles": [],
            "summary": summary,
            "cover_url": cover,
            "genres": (genres or ["Comic"])[: get_max_genres()],
            "tags": tags[: get_max_tags()],
            "year": year,
            "staff": staff[:10],
            "format": "comic",
            "url": url,
            "links": [url],
            "status": status,
        }
        if publisher:
            out["publisher"] = publisher
        return out

    def _first_cover(self, session, headers: Dict[str, str], hit: dict) -> Optional[str]:
        issues = hit.get("active_issues") or []
        if not issues:
            sid = self.extract_id_from_url(hit.get("api_url") or "")
            if not sid:
                return None
            detail = self._get_json(session, headers, f"{_API}/series/{sid}/")
            issues = (detail or {}).get("active_issues") or []
        if not issues:
            return None
        issue = self._get_json(session, headers, issues[0])
        return _norm_cover((issue or {}).get("cover"))
