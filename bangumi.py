"""Bangumi (bgm.tv) — métadonnées Manga / Light Novels via API publique (User-Agent requis)."""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional, Set

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_API = "https://api.bgm.tv"
_SITE = "https://bgm.tv"
_UA = "MetaKavita/1.0 (self-hosted; +https://github.com)"

# SubjectType Bangumi : 1 = Book (漫画 / 小说 / …)
_TYPE_BOOK = 1

_PLATFORM_MANGA = {"漫画", "漫画系列"}
_PLATFORM_NOVEL = {"小说", "小说系列"}

_AUTHOR_INFOBOX_KEYS = {"作者", "原作", "作画", "脚本"}
_PUBLISHER_KEYS = {"出版社"}
_ISBN_KEYS = {"ISBN", "ISBN-13", "ISBN-10"}
_NON_ISBN = re.compile(r"[^0-9Xx]")


def _normalize_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = _NON_ISBN.sub("", str(raw)).upper()
    if len(cleaned) in (10, 13):
        return cleaned
    return None


def _infobox_map(infobox: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not isinstance(infobox, list):
        return out
    for item in infobox:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key:
            continue
        out[str(key)] = item.get("value")
    return out


def _infobox_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for v in value:
            if isinstance(v, dict) and "v" in v:
                parts.append(str(v["v"]))
            elif isinstance(v, str):
                parts.append(v)
        return " / ".join(p.strip() for p in parts if p and str(p).strip())
    return str(value).strip()


def _wanted_platforms(library_type: str) -> Set[str]:
    if library_type == "Book":
        return set(_PLATFORM_NOVEL)
    if library_type in {"Manga", "Comic", "ComicFlexible"}:
        return set(_PLATFORM_MANGA)
    return set(_PLATFORM_MANGA) | set(_PLATFORM_NOVEL)


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


def _throttled_post(scraper, client, url: str, **kwargs):
    """POST cadencé, même contrat que `_throttled_get`."""
    helper = getattr(scraper, "_http_post", None)
    if callable(helper):
        return helper(client, url, **kwargs)
    _throttle_fallback(scraper)
    kwargs.setdefault("timeout", getattr(scraper, "http_timeout", 20.0))
    return client.post(url, **kwargs)


def _platform_ok(platform: Optional[str], wanted: Set[str]) -> bool:
    if not wanted:
        return True
    p = (platform or "").strip()
    if not p:
        return True  # indéterminé : on laisse passer, le scoring départage
    return p in wanted or any(w in p for w in wanted)


class BangumiScraper(BaseScraper):
    id = "BANGUMI"
    display_name = "Bangumi (JP/CN)"
    supported_types = {"Manga", "Book"}
    # 1.1.0 : toutes les requêtes d'un `fetch()` passent par la cadence, au lieu
    # d'une seule appliquée avant l'appel.
    version = "1.1.0"
    rate_limit = 1.2
    proxy_domains = ["bgm.tv", "api.bgm.tv", "lain.bgm.tv"]
    has_direct_id_support = True
    requires_proxy = False
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "direct_id": "🎯 [Bangumi] Requête subject id={0}",
            "search": "🔍 [Bangumi] Recherche pour '{0}'…",
            "no_match": "⚠️ [Bangumi] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Bangumi] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Bangumi] Erreur : {0}",
            "covers_err": "❌ [Covers] Erreur Bangumi : {0}",
        },
        "en": {
            "direct_id": "🎯 [Bangumi] Subject request id={0}",
            "search": "🔍 [Bangumi] Searching for '{0}'…",
            "no_match": "⚠️ [Bangumi] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Bangumi] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Bangumi] Error: {0}",
            "covers_err": "❌ [Covers] Bangumi error: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        url = url.strip()
        if url.isdigit():
            return url
        m = re.search(r"(?:bgm\.tv|bangumi\.tv)/subject/(\d+)", url)
        if m:
            return m.group(1)
        return None

    def fetch(
        self,
        query: str,
        library_type: str = "Manga",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session()
        try:
            if is_id:
                sid = self.extract_id_from_url(query) or (
                    query.strip() if str(query).strip().isdigit() else None
                )
                if not sid:
                    return None
                logging.info(self.t("direct_id").format(sid))
                detail = self._get_subject(session, int(sid))
                if not detail:
                    return None
                candidate = self._build_candidate(detail, library_type)
                if candidate:
                    return attach_match_score(candidate, 1.0)
                return None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None

            logging.info(self.t("search").format(cleaned))
            hits = self._search(session, cleaned, library_type)
            if not hits:
                return None

            wanted = _wanted_platforms(library_type)
            # Préférer les entrées série + bon platform
            ranked_hits = sorted(
                hits,
                key=lambda h: (
                    0 if h.get("series") else 1,
                    0 if _platform_ok(h.get("platform"), wanted) else 1,
                ),
            )

            best_match = None
            best_score = -1.0

            for hit in ranked_hits[:6]:
                sid = hit.get("id")
                if not sid:
                    continue
                # Filtre platform souple : skip volumes/autres si on a déjà un bon candidat
                if best_score >= 0.85 and not hit.get("series"):
                    continue
                if not _platform_ok(hit.get("platform"), wanted) and best_score >= 0.70:
                    continue

                detail = self._get_subject(session, int(sid))
                if not detail:
                    candidate = self._candidate_from_search_hit(hit, library_type)
                    platform = hit.get("platform")
                    is_series = bool(hit.get("series"))
                else:
                    if detail.get("type") not in (None, _TYPE_BOOK):
                        continue
                    if wanted and not _platform_ok(detail.get("platform"), wanted):
                        # laisser une chance si platform vide
                        if detail.get("platform"):
                            continue
                    candidate = self._build_candidate(detail, library_type)
                    platform = detail.get("platform")
                    is_series = bool(detail.get("series"))

                if not candidate or not candidate.get("title"):
                    continue

                score = score_candidate(candidate, cleaned, existing_metadata)
                if is_series:
                    score = min(1.0, score + 0.08)
                # Titre exact JP/CN/EN vs spin-off (ワンピースパーティー)
                names = [
                    (candidate.get("title") or ""),
                    *((candidate.get("alternative_titles") or [])[:4]),
                ]
                qcf = cleaned.casefold()
                exact = any((n or "").casefold() == qcf for n in names if n)
                if exact:
                    score = min(1.0, score + 0.18)
                else:
                    for n in names:
                        ncf = (n or "").casefold()
                        if qcf and qcf in ncf and ncf != qcf and len(ncf) > len(qcf) + 2:
                            score = max(0.0, score - 0.15)
                            break
                if _platform_ok(platform, wanted):
                    score = min(1.0, score + 0.05)

                if score > best_score:
                    best_score = score
                    best_match = candidate

            if not best_match or best_score < get_match_accept_threshold():
                logging.warning(
                    self.t("no_match").format(cleaned, int(max(best_score, 0) * 100))
                )
                return None

            logging.info(
                self.t("matched").format(best_match.get("title"), int(best_score * 100))
            )
            return attach_match_score(best_match, best_score)

        except Exception as e:
            logging.error(self.t("err").format(e))
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    def fetch_covers(
        self, query: str, library_type: str = "Manga"
    ) -> List[Dict[str, str]]:
        covers: List[Dict[str, str]] = []
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers

        session = requests.Session()
        try:
            hits = self._search(session, cleaned, library_type)
            wanted = _wanted_platforms(library_type)
            hits = sorted(
                hits,
                key=lambda h: (
                    0 if h.get("series") else 1,
                    0 if _platform_ok(h.get("platform"), wanted) else 1,
                ),
            )
            for hit in hits:
                if not _platform_ok(hit.get("platform"), wanted):
                    continue
                img = ((hit.get("images") or {}) or {}).get("large") or hit.get("image")
                title = hit.get("name_cn") or hit.get("name") or cleaned
                if img and img not in [c["url"] for c in covers]:
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": title,
                            "url": str(img).replace("http://", "https://"),
                        }
                    )
                if len(covers) >= 5:
                    break
        except Exception as e:
            logging.error(self.t("covers_err").format(e))
        finally:
            try:
                session.close()
            except Exception:
                pass
        return covers

    # ------------------------------------------------------------------ HTTP

    def _headers(self, *, json_body: bool = False) -> Dict[str, str]:
        h = {
            "User-Agent": _UA,
            "Accept": "application/json",
            "Accept-Language": "en,zh-CN;q=0.8,ja;q=0.6",
        }
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def _search(
        self, session, keyword: str, library_type: str
    ) -> List[Dict[str, Any]]:
        body: Dict[str, Any] = {
            "keyword": keyword,
            "sort": "match",
            "filter": {"type": [_TYPE_BOOK]},
        }
        # limit via query param on some versions — also in body for v0
        res = _throttled_post(
            self,
            session,
            f"{_API}/v0/search/subjects",
            headers=self._headers(json_body=True),
            params={"limit": 12},
            json=body,
            impersonate="chrome",
            timeout=20,
        )
        if res.status_code != 200:
            return []
        try:
            data = res.json()
        except Exception:
            return []
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        return [it for it in items if isinstance(it, dict) and it.get("id")]

    def _get_subject(self, session, subject_id: int) -> Optional[Dict[str, Any]]:
        res = _throttled_get(
            self,
            session,
            f"{_API}/v0/subjects/{subject_id}",
            headers=self._headers(),
            impersonate="chrome",
            timeout=20,
        )
        if res.status_code != 200:
            return None
        try:
            data = res.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    # ------------------------------------------------------------------ Build

    def _candidate_from_search_hit(
        self, hit: Dict[str, Any], library_type: str
    ) -> Optional[Dict[str, Any]]:
        title = (hit.get("name") or "").strip()
        if not title:
            return None
        name_cn = (hit.get("name_cn") or "").strip()
        alt = [name_cn] if name_cn and name_cn.casefold() != title.casefold() else []
        year = None
        date = hit.get("date") or ""
        m = re.match(r"^(\d{4})", str(date))
        if m:
            year = int(m.group(1))
        img = ((hit.get("images") or {}) or {}).get("large") or hit.get("image")
        if img:
            img = str(img).replace("http://", "https://")
        platform = hit.get("platform") or ""
        fmt = "book" if platform in _PLATFORM_NOVEL or library_type == "Book" else "manga"
        sid = hit.get("id")
        url = f"{_SITE}/subject/{sid}" if sid else None
        return {
            "title": title,
            "alternative_titles": alt,
            "summary": (hit.get("summary") or "").strip(),
            "cover_url": img,
            "genres": ["Manga"] if fmt == "manga" else ["Book"],
            "tags": [],
            "year": year,
            "staff": [],
            "publisher": None,
            "format": fmt,
            "url": url,
            "links": [url] if url else [],
        }

    def _build_candidate(
        self, detail: Dict[str, Any], library_type: str
    ) -> Optional[Dict[str, Any]]:
        # Rejeter anime / hors book
        if detail.get("type") not in (None, _TYPE_BOOK):
            return None

        title = (detail.get("name") or "").strip()
        if not title:
            return None

        name_cn = (detail.get("name_cn") or "").strip()
        alt: List[str] = []
        if name_cn and name_cn.casefold() != title.casefold():
            alt.append(name_cn)

        ib = _infobox_map(detail.get("infobox"))
        # alias from 别名
        aliases = ib.get("别名")
        if isinstance(aliases, list):
            for a in aliases:
                if isinstance(a, dict) and a.get("v"):
                    v = str(a["v"]).strip()
                    if v and v.casefold() != title.casefold() and v not in alt:
                        alt.append(v)
        elif isinstance(aliases, str) and aliases.strip():
            if aliases.strip() not in alt:
                alt.append(aliases.strip())

        authors: List[str] = []
        for key in _AUTHOR_INFOBOX_KEYS:
            raw = _infobox_text(ib.get(key))
            if raw:
                for part in re.split(r"[,，、/＆&]", raw):
                    name = part.strip()
                    if name and name not in authors:
                        authors.append(name)

        staff = [
            {"role": "Story", "node": {"name": {"full": name}}} for name in authors
        ]

        publisher = None
        for key in _PUBLISHER_KEYS:
            raw = _infobox_text(ib.get(key))
            if raw:
                # plusieurs éditeurs : premier
                publisher = re.split(r"[,，、/]", raw)[0].strip() or None
                break

        isbn = None
        for key in _ISBN_KEYS:
            n = _normalize_isbn(_infobox_text(ib.get(key)))
            if n:
                isbn = n
                if len(n) == 13:
                    break

        year = None
        date = detail.get("date") or _infobox_text(ib.get("发售日")) or _infobox_text(
            ib.get("开始")
        )
        m = re.search(r"(1[0-9]{3}|20[0-9]{2})", str(date))
        if m:
            year = int(m.group(1))

        # Status : 结束 présent → FINISHED ; 开始 sans 结束 → RELEASING
        status = None
        if _infobox_text(ib.get("结束")):
            status = "FINISHED"
        elif _infobox_text(ib.get("开始")) and not _infobox_text(ib.get("结束")):
            status = "RELEASING"

        tags = []
        genres = []
        for t in detail.get("tags") or []:
            if not isinstance(t, dict):
                continue
            name = (t.get("name") or "").strip()
            if not name:
                continue
            # genres grossiers
            if name in {"漫画", "轻小说", "小说", "少年", "少女", "青年", "BL", "GL"}:
                if name not in genres:
                    genres.append(name)
            else:
                tags.append(name)

        platform = (detail.get("platform") or "").strip()
        fmt = "book"
        if platform in _PLATFORM_MANGA or (
            library_type == "Manga" and platform not in _PLATFORM_NOVEL
        ):
            fmt = "manga"
        if library_type == "Book":
            fmt = "book"

        if not genres:
            genres = ["Manga"] if fmt == "manga" else ["Book"]

        img = ((detail.get("images") or {}) or {}).get("large")
        if img:
            img = str(img).replace("http://", "https://")

        sid = detail.get("id")
        url = f"{_SITE}/subject/{sid}" if sid else None
        summary = (detail.get("summary") or "").strip().replace("\r\n", "\n")

        # BF56 : nsfw Bangumi → erotica ; sinon omettre
        age_rating = "erotica" if detail.get("nsfw") is True else None

        candidate: Dict[str, Any] = {
            "title": title,
            "alternative_titles": alt,
            "summary": summary,
            "cover_url": img,
            "genres": genres[: get_max_genres()],
            "tags": tags[: get_max_tags()],
            "year": year,
            "staff": staff,
            "publisher": publisher,
            "format": fmt,
            "url": url,
            "links": [url] if url else [],
            "isbn": isbn,
        }
        if status:
            candidate["status"] = status
        if age_rating:
            candidate["age_rating"] = age_rating
        return candidate
