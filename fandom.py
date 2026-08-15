"""Fandom / Wikia — index de tomes via l'API MediaWiki de chaque wiki.

Magasin uniquement. On vise le wiki **EN** : c'est là que la liste des tomes
est la plus complète, et MetaKavita traduit à la volée. Les chemins `/fr/`
(et autres langues) sont ramenés au wiki EN.

Trois ancrages, du plus sûr au plus faible :

1. URL collée (Champ Magique / weblink) — `extract_id_from_url`
2. Slug dérivé du titre (`one piece` → `onepiece.fandom.com`)
3. DuckDuckGo HTML (`site:fandom.com`) — secours, pas un moteur dans la stack

Tous les tomes d'une série tiennent sur **une** page liste quand elle
existe. Un seul `action=parse` ramène titres, dates, ISBN, jaquettes et
chapitres. Sinon on lit les fiches `Volume N` (allpages + revisions).
Les synopsis wiki (`pageprops.fandomdescription`) viennent par lots de 50.
"""
from __future__ import annotations

import logging
import random
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from scrapers.base import BaseScraper
from scrapers.utils import (
    album_number_key,
    attach_match_score,
    calculate_similarity,
    clean_title,
    extract_volume_number,
    get_match_accept_threshold,
    score_candidate,
)

# --- Cadence (repli images antérieures à `_http_get`) ------------------------
_LAST_CALL: dict = {}
_LAST_CALL_LOCK = threading.Lock()

RATE_LIMIT_MIN = 4.0
RATE_LIMIT_MAX = 8.0

_FANDOM_HOST = re.compile(
    r"^https?://(?:(?P<sublang>[a-z]{2})\.)?(?P<wiki>[a-z0-9-]+)\.(?:fandom|wikia)\.com"
    r"(?:/(?P<pathlang>[a-z]{2})(?=/wiki|/api\.php|/?$))?"
    r"(?:/wiki/(?P<page>[^?#]+))?",
    re.I,
)
_ISBN13 = re.compile(r"(97[89]\d{10})")
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_ISO_DATE = re.compile(r"(1[0-9]{3}|20[0-9]{2})-(\d{2})-(\d{2})")
_MDY = re.compile(
    r"\b([A-Za-zÀ-ÿ]{3,9})\s+(\d{1,2}),?\s+(1[0-9]{3}|20[0-9]{2})\b"
)
_DMY = re.compile(
    r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,9})\s+(1[0-9]{3}|20[0-9]{2})\b"
)
_VOLUME_HEAD = re.compile(
    r"^\s*(?:volume|vol\.?|tome|tomo)\s*(\d+(?:[.,]\d+)?)\s*$",
    re.I,
)
_PLACEHOLDER_IMG = re.compile(r"^data:image/|^https?://.*1x1", re.I)
_WIKI_HREF = re.compile(r"/wiki/([^?#]+)", re.I)
_COVER_BLURB = re.compile(
    r"\b(colored cover|the cover (has|is|uses|features)|title logo|"
    r"spine features|background, and the title)\b",
    re.I,
)
_SKIP_WIKI_NS = (
    "special:",
    "file:",
    "category:",
    "template:",
    "help:",
    "user:",
    "talk:",
)
PAGEPROPS_BATCH = 50
SUMMARY_MAX = 2000
_REJECT_WIKI = {
    "community",
    "fandom",
    "vsbattles",
    "any-anime",
    "fanon",
    "fanfiction",
    "shipping",
}

# Pages liste EN, la plus spécifique d'abord. Un `parse` de la première
# qui existe rend l'index entier (One Piece : 100+ tomes, une requête).
_VOLUME_LIST_TITLES = (
    "Chapters and Volumes/Volumes",
    "List of Volumes",
    "List of Volumes and Chapters",
    "Volumes & Chapters",
    "Releases (Manga)",
    "Volume List",
    "Chapters and Volumes",
    "Volumes",
)
_WIKI_ALIASES = {
    "jojo's bizarre adventure": ("jojo",),
    "jojos bizarre adventure": ("jojo",),
    "komi can't communicate": ("komisan",),
    "komi cant communicate": ("komisan",),
    "kaguya-sama": ("kaguyasama-wa-kokurasetai",),
    "kaguya sama": ("kaguyasama-wa-kokurasetai",),
    "the apothecary diaries": ("kusuriya-no-hitorigoto",),
    "apothecary diaries": ("kusuriya-no-hitorigoto",),
}
_SKIP_VOLUME_PAGE = re.compile(
    r"blu-?ray|\bdvd\b|bd&dvd|light novel|episode nagi|\bspecial\b|\bextra\b|\banime\b",
    re.I,
)
_LOCALIZED_PAGE = re.compile(
    r"liste des|\btomes\b|\bchapitres\b|\bbände\b|\btomos\b",
    re.I,
)

_VOLUME_TEMPLATE_NAMES = {
    "volume",
    "volume123",
    "volinfo",
    "volumelist",
    "volume list",
    "volume box",
    "template:volume box",
    "volume infobox",
    "volumeinfobox",
    "tankobon",
    "volumes",
    "infobox:volume",
    "infobox volume",
}
_DDG_SKIP_WIKI = {
    "manga",
    "comic",
    "anime",
    "kodansha-comics",
    "shonen-magazine",
    "animax",
    "dubbing",
    "hero",
    "darkhorse",
}
_WIKITEXT_HEADING = re.compile(r"^==\s*(.+?)\s*==\s*$", re.M)

_MONTHS = {
    "january": 1, "jan": 1, "janvier": 1, "enero": 1,
    "february": 2, "feb": 2, "février": 2, "fevrier": 2, "febrero": 2,
    "march": 3, "mar": 3, "mars": 3, "marzo": 3,
    "april": 4, "apr": 4, "avril": 4, "abril": 4,
    "may": 5, "mai": 5, "mayo": 5,
    "june": 6, "jun": 6, "juin": 6, "junio": 6,
    "july": 7, "jul": 7, "juillet": 7, "julio": 7,
    "august": 8, "aug": 8, "août": 8, "aout": 8, "agosto": 8,
    "september": 9, "sep": 9, "sept": 9, "septembre": 9, "septiembre": 9,
    "october": 10, "oct": 10, "octobre": 10, "octubre": 10,
    "november": 11, "nov": 11, "novembre": 11, "noviembre": 11,
    "december": 12, "dec": 12, "décembre": 12, "decembre": 12, "diciembre": 12,
}


def _throttle_fallback(scraper) -> None:
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
    """GET cadencé, avec jitter 4–8 s sur l'instance (le catalogue garde 6.0)."""
    scraper.rate_limit = random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX)
    helper = getattr(scraper, "_http_get", None)
    if callable(helper):
        return helper(client, url, **kwargs)
    _throttle_fallback(scraper)
    kwargs.setdefault("timeout", getattr(scraper, "http_timeout", 20.0))
    return client.get(url, **kwargs)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold()


def series_name_to_slugs(name: str) -> List[str]:
    """Candidats de sous-domaine Fandom à partir du titre de série.

    `One Piece` → `onepiece` ; `Attack on Titan` → `attackontitan` puis
    `attack-on-titan`. Le premier slug compact est celui que Fandom utilise
    le plus souvent. On ne dérive pas le premier mot seul (`one`) : trop de
    collisions.
    """
    cleaned = clean_title(name) or (name or "")
    folded = _fold(cleaned)
    folded = folded.replace("'s", "s").replace("'", "")
    compact = re.sub(r"[^a-z0-9]+", "", folded)
    dashed = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    out: List[str] = []
    for slug in (compact, dashed):
        if slug and len(slug) >= 3 and slug not in out:
            out.append(slug)
    # Titres à article : `A Couple of Cuckoos` n'est pas `acoupleofcuckoos.fandom.com`.
    stripped = re.sub(r"^(?:a|an|the|le|la|les|l|el|los|las)\s+", "", folded)
    if stripped != folded:
        alt = re.sub(r"[^a-z0-9]+", "", stripped)
        if alt and len(alt) >= 3 and alt not in out:
            out.append(alt)
    aliases = wiki_alias_slugs(cleaned)
    extras: List[str] = []
    words = [w for w in re.findall(r"[a-z0-9]+", folded) if len(w) >= 5]
    if words:
        last = words[-1]
        if last.endswith("s") and len(last) >= 6:
            stem = last[:-1]
            if stem not in out:
                extras.append(stem)
        if last not in out and last not in extras:
            extras.append(last)
    for slug in aliases + extras:
        if slug and slug not in out:
            out.append(slug)
    return out


def wiki_alias_slugs(name: str) -> List[str]:
    """Slugs wiki qui ne se déduisent pas du titre EN (JoJo → jojo, etc.)."""
    folded = _fold(name)
    folded = folded.replace("'s", "s").replace("'", "")
    out: List[str] = []
    for key, aliases in _WIKI_ALIASES.items():
        key_fold = _fold(key).replace("'s", "s").replace("'", "")
        if folded == key_fold or folded.startswith(key_fold + " ") or folded.startswith(key_fold + ":"):
            for alias in aliases:
                if alias not in out:
                    out.append(alias)
    return out


def series_alt_titles(query: str, sitename: str, wiki: str) -> List[str]:
    """Titres secondaires pour le score : sitename seul rate `Hunterpedia`."""
    seen = {_fold(sitename)}
    out: List[str] = []
    candidates = [wiki.replace("-", " ")]
    for slug in series_name_to_slugs(query)[:2]:
        candidates.append(slug.replace("-", " "))
    for raw in candidates:
        text = re.sub(r"\s+", " ", raw or "").strip()
        if not text or _fold(text) in seen:
            continue
        seen.add(_fold(text))
        out.append(text)
    return out


def series_name_to_wiki_url(name: str, *, lang: str = "") -> str:
    """URL de wiki la plus probable pour ce titre — non vérifiée réseau."""
    slugs = series_name_to_slugs(name)
    if not slugs:
        return ""
    slug = slugs[0]
    lang = (lang or "").strip().lower()[:2]
    if lang and lang != "en":
        return f"https://{slug}.fandom.com/{lang}/"
    return f"https://{slug}.fandom.com/"


@dataclass(frozen=True)
class FandomRef:
    wiki: str
    page: str = ""
    lang: str = ""

    def api_url(self) -> str:
        if self.lang and self.lang != "en":
            return f"https://{self.wiki}.fandom.com/{self.lang}/api.php"
        return f"https://{self.wiki}.fandom.com/api.php"

    def page_url(self, page: Optional[str] = None) -> str:
        title = (page if page is not None else self.page) or ""
        title = title.replace(" ", "_")
        if self.lang and self.lang != "en":
            base = f"https://{self.wiki}.fandom.com/{self.lang}/wiki"
        else:
            base = f"https://{self.wiki}.fandom.com/wiki"
        return f"{base}/{title}" if title else f"{base}/"

    def token(self) -> str:
        base = f"{self.wiki}/{self.lang}" if self.lang and self.lang != "en" else self.wiki
        return f"{base}:{self.page}" if self.page else base


def to_en_wiki(ref: FandomRef) -> FandomRef:
    """Wiki EN uniquement : plus de tomes, et la traduction est côté MetaKavita.

    Une URL `/fr/wiki/Liste_des_tomes` ne pointe pas vers la liste EN : on
    garde le sous-domaine et on laisse le parse trouver la page liste anglaise.
    Un titre de page déjà anglais (`Chapters and Volumes/Volumes`) est conservé.
    """
    page = ref.page
    if page and _LOCALIZED_PAGE.search(page):
        page = ""
    return FandomRef(wiki=ref.wiki, page=page, lang="")


def parse_fandom_url(url: str) -> Optional[FandomRef]:
    raw = str(url or "").strip()
    if not raw:
        return None
    match = _FANDOM_HOST.match(raw)
    if not match:
        return None
    wiki = (match.group("wiki") or "").lower()
    if not wiki or wiki in _REJECT_WIKI:
        return None
    lang = (match.group("pathlang") or match.group("sublang") or "").lower()
    if lang == "en":
        lang = ""
    page = unquote(match.group("page") or "").strip().strip("/")
    page = page.replace("_", " ")
    return FandomRef(wiki=wiki, page=page, lang=lang)


def parse_fandom_token(token: str) -> Optional[FandomRef]:
    raw = str(token or "").strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return parse_fandom_url(raw)
    wiki_part, _, page = raw.partition(":")
    wiki_part = wiki_part.strip().lower()
    page = page.replace("_", " ").strip()
    if "/" in wiki_part:
        wiki, lang = wiki_part.split("/", 1)
        lang = lang.strip().lower()[:2]
    else:
        wiki, lang = wiki_part, ""
    if not re.fullmatch(r"[a-z0-9-]{3,64}", wiki) or wiki in _REJECT_WIKI:
        return None
    return FandomRef(wiki=wiki, page=page, lang=lang if lang != "en" else "")


def unwrap_ddg_href(href: str) -> str:
    raw = str(href or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    uddg = parse_qs(parsed.query).get("uddg") or []
    if uddg:
        return unquote(uddg[0])
    return raw


def to_iso_date(text: str) -> str:
    """« December 24, 1997 » / « 26 November 1990 » → `YYYY-MM-DD` (Kavita)."""
    raw = re.sub(r"\[[^\]]*\]", " ", str(text or ""))
    raw = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", raw, flags=re.I)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return ""
    iso = _ISO_DATE.search(raw)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    mdy = _MDY.search(raw)
    if mdy:
        month = _MONTHS.get(_fold(mdy.group(1)))
        if month:
            return f"{mdy.group(3)}-{month:02d}-{int(mdy.group(2)):02d}"
    dmy = _DMY.search(raw)
    if dmy:
        month = _MONTHS.get(_fold(dmy.group(2)))
        if month:
            return f"{dmy.group(3)}-{month:02d}-{int(dmy.group(1)):02d}"
    year = _YEAR.search(raw)
    return year.group(1) if year else ""


def split_edition_dates(text: str) -> Tuple[str, str]:
    """`May 15th, 2020 (JP)<br>January 12th, 2021 (US)` → (en_iso, ja_iso)."""
    en = ja = unlabeled = ""
    chunks = re.split(r"<br\s*/?>|\n", text or "")
    if len(chunks) <= 1:
        chunks = re.split(r"(?<=\))\s+", text or "") or [text or ""]
    for chunk in chunks:
        iso = to_iso_date(chunk)
        if not iso:
            continue
        folded = _fold(chunk)
        if re.search(r"\b(?:us|en|english)\b", folded):
            en = en or iso
        elif re.search(r"\b(?:jp|ja|japanese)\b", folded):
            ja = ja or iso
        else:
            unlabeled = unlabeled or iso
    return en or unlabeled, ja or unlabeled


def first_isbn(text: str, *, prefer_en: bool = True) -> str:
    compact = re.sub(r"[^0-9Xx]", "", str(text or ""))
    found = _ISBN13.findall(compact)
    if not found:
        return ""
    if prefer_en:
        western = [isbn for isbn in found if not isbn.startswith("9784")]
        if western:
            return western[0]
    return found[0]


def upgrade_cover(url: Optional[str]) -> str:
    raw = str(url or "").strip()
    if not raw or _PLACEHOLDER_IMG.search(raw):
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    raw = raw.split("?")[0]
    raw = re.sub(r"/revision/latest/scale-to-width-down/\d+", "/revision/latest", raw)
    return raw


def page_from_href(href: str) -> str:
    match = _WIKI_HREF.search(href or "")
    if not match:
        return ""
    title = unquote(match.group(1)).replace("_", " ").strip()
    folded = title.casefold()
    if any(folded.startswith(ns) for ns in _SKIP_WIKI_NS):
        return ""
    return title


def wikitext_to_text(raw: str) -> str:
    """Aplatit liens / petits templates pour un résumé lisible."""
    text = str(raw or "")
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\{\{\s*e\s*\|\s*([^}]+)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"^\*+\s*", "", text, flags=re.M)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_summary(text: str) -> str:
    raw = unescape(re.sub(r"\[[^\]]*\]", " ", str(text or "")))
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = re.sub(r"\s*See also\.?\s*$", "", raw, flags=re.I)
    if raw.endswith("..."):
        raw = raw[:-3].rstrip()
    return raw


def is_cover_blurb(text: str) -> bool:
    return bool(_COVER_BLURB.search(text or ""))


def pick_summary(
    *,
    plot: str = "",
    chapters: str = "",
    cover: str = "",
    extra: str = "",
) -> str:
    parts: List[str] = []
    if plot:
        parts.append(plot)
        if chapters and chapters.casefold() not in plot.casefold():
            parts.append(chapters)
    elif chapters:
        parts.append(chapters)
    elif cover:
        parts.append(cover)
    elif extra:
        parts.append(extra)
    text = "\n\n".join(part for part in parts if part)
    if len(text) > SUMMARY_MAX:
        text = text[: SUMMARY_MAX - 1].rsplit(" ", 1)[0] + "…"
    return text


def format_chapter_summary(titles: List[str]) -> str:
    lines = []
    for i, title in enumerate(titles, 1):
        name = (title or "").strip()
        if not name:
            continue
        lines.append(f"{i}. {name}")
    return "\n".join(lines)


def _chapter_titles(node) -> List[str]:
    titles: List[str] = []
    for li in node.find_all("li"):
        anchor = li.find("a", href=_WIKI_HREF)
        text = anchor.get_text(" ", strip=True) if anchor else li.get_text(" ", strip=True)
        text = re.sub(r"^\d+\.?\s*", "", text)
        text = text.strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
            text = text[1:-1].strip()
        if text and _fold(text) not in {"chapters", "cover character(s)", "cover characters"}:
            titles.append(text)
        if len(titles) >= 40:
            break
    return titles


def _chapters_from_node(node) -> List[str]:
    for dt in node.find_all("dt"):
        if "chapter" not in _fold(dt.get_text(" ", strip=True)):
            continue
        dl = dt.find_parent("dl")
        ul = None
        if dl is not None:
            ul = dl.find_next_sibling("ul") or dl.find("ul")
        if ul is None:
            ul = dt.find_next("ul")
        if ul is not None:
            return _chapter_titles(ul)
    for ul in node.find_all("ul"):
        items = _chapter_titles(ul)
        blob = ul.get_text(" ", strip=True)
        if items and re.search(r"\b\d{1,3}\.\s", blob):
            return items
    return []


def _public_index(index: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for key, payload in index.items():
        clean = {field: value for field, value in payload.items() if value and not field.startswith("_")}
        if clean:
            out[key] = clean
    return out


def _template_params(body: str) -> Dict[str, str]:
    """Découpe `Name|k=v|k2=v2` en ignorant les `{{…}}` imbriqués."""
    parts: List[str] = [""]
    depth = 0
    i = 0
    while i < len(body):
        if body.startswith("{{", i):
            depth += 1
            parts[-1] += "{{"
            i += 2
            continue
        if body.startswith("}}", i):
            depth = max(0, depth - 1)
            parts[-1] += "}}"
            i += 2
            continue
        if body[i] == "|" and depth == 0:
            parts.append("")
            i += 1
            continue
        parts[-1] += body[i]
        i += 1
    params: Dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip().lower()
        if key:
            params[key] = value.strip()
    return params


def iter_templates(wikitext: str, names: Iterable[str]) -> Iterable[Tuple[str, Dict[str, str]]]:
    wanted = {n.lower() for n in names}
    i = 0
    text = wikitext or ""
    while True:
        start = text.find("{{", i)
        if start < 0:
            return
        depth = 1
        k = start + 2
        while k < len(text) - 1 and depth:
            if text.startswith("{{", k):
                depth += 1
                k += 2
                continue
            if text.startswith("}}", k):
                depth -= 1
                if depth == 0:
                    body = text[start + 2 : k]
                    k += 2
                    break
                k += 2
                continue
            k += 1
        else:
            return
        i = k
        name = body.split("|", 1)[0].strip().lower()
        if name in wanted:
            yield name, _template_params(body)


def _param(params: Dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (params.get(key) or "").strip()
        if value:
            return value
    return ""


def parse_wikitext_volumes(wikitext: str, *, prefer_en: bool = True) -> Dict[str, Dict[str, str]]:
    """Tomes exposés par `{{Volume}}` / `{{volinfo}}` / `{{Tankobon}}` / `{{Volumes}}`."""
    index: Dict[str, Dict[str, str]] = {}
    for _name, params in iter_templates(wikitext, _VOLUME_TEMPLATE_NAMES):
        number = album_number_key(
            _param(params, "#", "volume", "vol", "no", "vol_num")
        ) or volume_number_from_title(
            _param(params, "vol_num", "title")
        )
        if not number:
            continue
        us_title = _param(
            params, "us title", "en title", "engname", "en_title", "title"
        )
        jp_title = _param(params, "jp title", "ja title", "jpname", "title_jp")
        title = us_title if (prefer_en and us_title) else (jp_title or us_title)
        title = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", title)
        title = re.sub(r"\[\[|\]\]", "", title)
        title = re.sub(r"'{2,}", "", title).strip()
        title = clean_volume_title(title, number=number)
        release_blob = " ".join(
            _param(params, key)
            for key in (
                "release",
                "eng release",
                "en release",
                "jp release",
                "ja release",
            )
        )
        release_en, release_ja = split_edition_dates(release_blob)
        en_date = to_iso_date(
            _param(
                params,
                "en pub",
                "us date",
                "date en",
                "eng_release",
                "release eng",
                "release_en",
                "date_en",
                "eng release",
                "en release",
            )
        ) or release_en
        ja_date = to_iso_date(
            _param(
                params,
                "ja pub",
                "jp date",
                "date jp",
                "jap_release",
                "release jp",
                "release_ja",
                "date_jp",
                "jp release",
                "ja release",
                "date",
            )
        ) or release_ja
        isbn = first_isbn(
            " ".join(
                _param(params, key)
                for key in (
                    "isbn",
                    "en isbn",
                    "isbn en",
                    "eng_isbn",
                    "isbn eng",
                    "isbn_en",
                    "isbn13_en",
                    "isbn jp",
                    "jap_isbn",
                    "isbn_ja",
                    "isbn13_jp",
                    "isbn ja",
                    "eng release",
                    "jp release",
                    "en release",
                )
            ),
            prefer_en=prefer_en,
        )
        explicit = wikitext_to_text(
            params.get("summary")
            or params.get("synopsis")
            or params.get("description")
            or ""
        )
        extra_bits = [
            wikitext_to_text(params.get(key) or "")
            for key in ("arcs", "episodes", "chapters")
        ]
        extra = "\n".join(bit for bit in extra_bits if bit)
        payload = {
            "title": title,
            "release_date": en_date or ja_date if prefer_en else ja_date or en_date,
            "isbn": isbn,
            "summary": explicit,
            "_extra": extra,
        }
        payload = {k: v for k, v in payload.items() if v}
        if payload:
            index[number] = payload
    return index


def wikitext_section(raw: str, names: Iterable[str]) -> str:
    wanted = {_fold(name) for name in names}
    parts = _WIKITEXT_HEADING.split(raw or "")
    i = 1
    while i + 1 < len(parts):
        if _fold(parts[i]) in wanted:
            return parts[i + 1].strip()
        i += 2
    return ""


def parse_volume_page_wikitext(
    wikitext: str,
    *,
    fallback_number: str = "",
    prefer_en: bool = True,
) -> Dict[str, str]:
    """Une fiche `Volume N` : infobox + Synopsis + Chapters (wikis sans page liste)."""
    index = parse_wikitext_volumes(wikitext, prefer_en=prefer_en)
    payload = dict(index.get(fallback_number) or next(iter(index.values()), {}) or {})
    if fallback_number:
        payload.setdefault("_page", f"Volume {fallback_number}")
    synopsis = wikitext_to_text(wikitext_section(wikitext, ("synopsis", "plot", "summary")))
    if synopsis:
        payload["summary"] = synopsis
    chapter_body = wikitext_section(wikitext, ("chapters", "chapter list"))
    titles = []
    for match in re.finditer(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", chapter_body):
        name = match.group(1).strip()
        name = re.sub(r"^(?:chapter|root)\s*\d+[.:]?\s*", "", name, flags=re.I)
        if name:
            titles.append(name)
    if titles:
        payload["_chapters"] = format_chapter_summary(titles)
    return {k: v for k, v in payload.items() if v}


def volume_number_from_title(title: str) -> Optional[str]:
    """`Volume 1` / `Vol. 2.5` → clé d'album. `album_number_key` seul refuse le texte."""
    text = (title or "").strip()
    match = _VOLUME_HEAD.match(text)
    if match:
        return album_number_key(match.group(1))
    extracted = extract_volume_number(text)
    if extracted is not None:
        return album_number_key(extracted)
    return album_number_key(text)


def score_ddg_ref(query: str, ref: FandomRef, slugs: Iterable[str]) -> int:
    if ref.wiki in _REJECT_WIKI or ref.wiki in _DDG_SKIP_WIKI:
        return -1
    points = 0
    if ref.wiki in set(slugs):
        points += 20
    page = _fold(ref.page)
    page_score = calculate_similarity(query, ref.page or "")
    wiki_score = calculate_similarity(query, ref.wiki)
    if page_score >= 0.55:
        points += 12
    if "volume" in page or "tome" in page:
        points += 8
    if page.endswith("/volumes") or page in {_fold(t) for t in _VOLUME_LIST_TITLES}:
        points += 6
    if points <= 0 and max(page_score, wiki_score) < 0.45:
        return -1
    return points


def _cell_text(cell) -> str:
    return cell.get_text(" ", strip=True) if cell is not None else ""


def _table_cover(table) -> str:
    for img in table.find_all("img"):
        cover = upgrade_cover(img.get("data-src") or img.get("src"))
        if cover:
            return cover
    return ""


def _is_volume_data_table(table) -> bool:
    blob = table.get_text(" ", strip=True).lower()
    return "isbn" in blob or "release date" in blob or "publication" in blob


def _header_page(cell) -> str:
    if cell is None:
        return ""
    link = cell.find("a", href=True)
    if link is None:
        return ""
    return page_from_href(link.get("href") or "") or (link.get("title") or "").replace("_", " ")


def parse_html_volume_blocks(html: str, *, prefer_en: bool = True) -> Dict[str, Dict[str, str]]:
    """Tables « Volume N » + Title / Release Date / ISBN (modèle One Piece)."""
    soup = BeautifulSoup(html or "", "html.parser")
    index: Dict[str, Dict[str, str]] = {}
    for table in soup.find_all("table"):
        if not _is_volume_data_table(table):
            continue
        rows = table.find_all("tr")
        if not rows:
            continue
        head_cell = rows[0].find(["th", "td"])
        head = _cell_text(head_cell)
        number = None
        match = _VOLUME_HEAD.match(head)
        if match:
            number = album_number_key(match.group(1))
        if not number:
            continue
        edition_rows: List[Tuple[str, List[str]]] = []
        for row in rows[1:]:
            cells = [_cell_text(c) for c in row.find_all(["th", "td"])]
            if len(cells) < 3:
                continue
            label = _fold(cells[0])
            edition_rows.append((label, cells))
        chosen: Optional[List[str]] = None
        for label, cells in edition_rows:
            if prefer_en and label in {"us", "en", "english", "usa"}:
                chosen = cells
                break
            if not prefer_en and label in {"japan", "jp", "ja", "japanese"}:
                chosen = cells
                break
        if chosen is None:
            for label, cells in edition_rows:
                if label not in {"x", "title", "release date", "pages", "isbn", "chapters"}:
                    chosen = cells
                    break
        if not chosen:
            continue
        title = chosen[1] if len(chosen) > 1 else ""
        if title.upper() in {"TBA", "TBD", "N/A", "?"} or _looks_like_date_title(title):
            title = ""
            if prefer_en and len(chosen) > 2:
                release_guess = to_iso_date(chosen[2]) or to_iso_date(chosen[1] if len(chosen) > 1 else "")
            else:
                release_guess = to_iso_date(chosen[1] if len(chosen) > 1 else "") or to_iso_date(
                    chosen[2] if len(chosen) > 2 else ""
                )
        else:
            release_guess = ""
        for row in rows[1:]:
            cells = [_cell_text(c) for c in row.find_all(["th", "td"])]
            cand = cells[0] if cells else ""
            if title or not cand or _VOLUME_HEAD.match(cand) or _looks_like_date_title(cand):
                continue
            if clean_volume_title(cand, number=number or ""):
                title = cand
                break
        title = clean_volume_title(title, number=number or "")
        release = release_guess or to_iso_date(chosen[2] if len(chosen) > 2 else "")
        isbn = ""
        for cell in chosen:
            isbn = first_isbn(cell, prefer_en=prefer_en)
            if isbn:
                break
        payload = {
            "title": title,
            "release_date": release,
            "isbn": isbn,
            "cover_url": _table_cover(table),
            "_chapters": format_chapter_summary(_chapters_from_node(table)),
            "_page": _header_page(head_cell),
        }
        payload = {k: v for k, v in payload.items() if v}
        if payload:
            index[number] = payload
    return index


def _cell_release_date(text: str) -> str:
    raw = str(text or "")
    if _ISBN13.search(re.sub(r"[^0-9Xx]", "", raw)):
        return ""
    return to_iso_date(raw)


def _looks_like_date_title(text: str) -> bool:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    return bool(_DMY.fullmatch(raw) or _MDY.fullmatch(raw) or _ISO_DATE.fullmatch(raw))


def clean_volume_title(title: str, *, number: str = "") -> str:
    """Jette les titres qui sont une date, un label d'infobox, ou `Volume N`."""
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return ""
    folded = _fold(text)
    if folded in {"tba", "tbd", "n/a", "?", "chapters", "pages", "isbn"}:
        return ""
    if number and folded == f"volume {number}":
        return ""
    if _looks_like_date_title(text):
        return ""
    if to_iso_date(text) and len(text) <= 28:
        return ""
    if re.match(r"(?i)^(pages|cover character|isbn|release)\b", text):
        return ""
    return text


def is_indexable_volume_page(title: str) -> bool:
    """`Volume 1` / `Manga Volume 01` — pas les Blu-ray ni Episode Nagi."""
    text = (title or "").strip()
    if not text or _SKIP_VOLUME_PAGE.search(text):
        return False
    if _VOLUME_HEAD.match(text):
        return True
    return bool(re.match(r"(?i)^(?:manga\s+)?volume\s+\d+", text))


def index_missing_bibliography(index: Dict[str, Dict[str, str]]) -> bool:
    if not index:
        return True
    filled = sum(1 for payload in index.values() if payload.get("release_date") or payload.get("isbn"))
    return filled * 4 < len(index)


def is_volume_page_title(title: str) -> bool:
    text = (title or "").strip()
    folded = _fold(text)
    return bool(re.search(r"\bvolume\b", folded) or _VOLUME_HEAD.match(text))


def parse_html_list_volumes(html: str, *, prefer_en: bool = True) -> Dict[str, Dict[str, str]]:
    """Table unique « # / titre / dates » (modèle Naruto / SMW)."""
    soup = BeautifulSoup(html or "", "html.parser")
    index: Dict[str, Dict[str, str]] = {}
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        head_cell = rows[0].find(["th", "td"])
        if _VOLUME_HEAD.match(_cell_text(head_cell)):
            continue
        headers = [_fold(_cell_text(cell)) for cell in rows[0].find_all(["th", "td"])]
        if len(headers) < 3:
            continue
        if not any(
            token in header
            for header in headers
            for token in ("release", "date", "isbn", "publication")
        ):
            continue
        if not any(
            token in header for header in headers for token in ("title", "name", "arc")
        ):
            continue
        if headers[0] not in {"#", "no", "no.", "n°", "nº", "vol", "volume", "n", ""}:
            continue
        parsed: Dict[str, Dict[str, str]] = {}
        i = 1
        while i < len(rows):
            cells = rows[i].find_all(["th", "td"])
            number = album_number_key(_cell_text(cells[0])) if cells else None
            if not number or len(cells) < 2:
                i += 1
                continue
            title_cell = cells[1]
            link = title_cell.find("a", href=_WIKI_HREF)
            link_title = link.get_text(" ", strip=True) if link else ""
            full_title = _cell_text(title_cell)
            if any("title" in header or "name" in header for header in headers):
                title = link_title or full_title
            else:
                title = full_title or link_title
            title = clean_volume_title(title, number=number or "")
            page = ""
            if link is not None:
                page = page_from_href(link.get("href") or "") or (link.get("title") or "").replace("_", " ")
            if page and not is_volume_page_title(page):
                page = ""
            date_cells = [_cell_text(cell) for cell in cells[2:]]
            release = ""
            ordered = reversed(date_cells) if prefer_en else date_cells
            for cell in ordered:
                release = _cell_release_date(cell)
                if release:
                    break
            isbn = ""
            for cell in cells:
                isbn = first_isbn(_cell_text(cell), prefer_en=prefer_en)
                if isbn:
                    break
            chapters = ""
            cover = ""
            if i + 1 < len(rows):
                nxt = rows[i + 1]
                nxt_cells = nxt.find_all(["th", "td"])
                nxt_number = album_number_key(_cell_text(nxt_cells[0])) if nxt_cells else None
                if not nxt_number and nxt.find("ul"):
                    chapters = format_chapter_summary(_chapters_from_node(nxt))
                    cover = _table_cover(nxt)
                    i += 1
            payload = {
                "title": title,
                "release_date": release,
                "isbn": isbn,
                "cover_url": cover,
                "_chapters": chapters,
                "_page": page,
            }
            payload = {k: v for k, v in payload.items() if v}
            if payload:
                parsed[number] = payload
            i += 1
        index = merge_volume_payloads(index, parsed)
    return index


def parse_html_volumes(html: str, *, prefer_en: bool = True) -> Dict[str, Dict[str, str]]:
    """Index HTML : blocs One Piece d'abord, table-liste ensuite."""
    blocks = parse_html_volume_blocks(html, prefer_en=prefer_en)
    listed = parse_html_list_volumes(html, prefer_en=prefer_en)
    return merge_volume_payloads(blocks, listed)


def merge_volume_payloads(
    primary: Dict[str, Dict[str, str]],
    secondary: Dict[str, Dict[str, str]],
) -> Dict[str, Dict[str, str]]:
    merged = {key: dict(payload) for key, payload in primary.items()}
    for key, payload in secondary.items():
        current = merged.setdefault(key, {})
        for field, value in payload.items():
            if value and field not in current:
                current[field] = value
    return merged


def pages_to_parse(ref: FandomRef) -> List[str]:
    """Ordre des pages à `parse` : une réussite suffit, elle porte tous les tomes."""
    ordered: List[str] = []
    if ref.page:
        folded = _fold(ref.page)
        if folded == "chapters and volumes":
            ordered.append("Chapters and Volumes/Volumes")
        ordered.append(ref.page)
    for title in _VOLUME_LIST_TITLES:
        if title not in ordered:
            ordered.append(title)
    return ordered


def score_volume_list_title(title: str) -> int:
    text = (title or "").strip()
    folded = _fold(text)
    if any(bad in folded for bad in ("fanon", "anime)", "episode list")):
        return -1
    if _VOLUME_HEAD.match(text) or re.search(r"\bvolume \d+\b", folded):
        return 1
    score = 0
    if folded in {
        "list of volumes",
        "chapters and volumes",
        "chapters and volumes/volumes",
        "releases (manga)",
        "liste des tomes",
        "liste des volumes",
    }:
        score += 12
    if folded.endswith("/volumes"):
        score += 8
    if "volume" in folded or "tome" in folded:
        score += 4
    if "chapter" in folded or "chapitre" in folded:
        score += 2
    if "(anime)" in folded:
        score -= 6
    return score


def _clean_sitename(sitename: str) -> str:
    text = re.sub(r"\s+wiki(?:a)?\s*$", "", sitename or "", flags=re.I).strip()
    return text


class FandomScraper(BaseScraper):
    id = "FANDOM"
    display_name = "Fandom (Wikis)"
    supported_types = {"Manga", "Comic", "Book"}
    scopes = {"series", "volume"}
    # 6.0 = moyenne documentée ; chaque requête tire uniformément dans [4, 8].
    rate_limit = 6.0
    http_timeout = 25.0
    version = "1.4.1"
    proxy_domains = [
        "fandom.com",
        "wikia.com",
        "wikia.nocookie.net",
        "static.wikia.nocookie.net",
        "images.wikia.com",
    ]
    has_direct_id_support = True
    uses_unified_scoring = True
    needs_api_key = False
    requires_proxy = True
    VOLUME_INDEX_MAX = 200

    translations = {
        "fr": {
            "display_name": "Fandom (Wikis)",
            "direct_url": "[Fandom] URL / identifiant : '{0}'",
            "search_title": "[Fandom] Recherche du wiki pour : '{0}'",
            "no_match": "⚠️ [Fandom] Aucun wiki pertinent pour '{0}' (score max: {1}%)",
            "matched": "🎯 [Fandom] Wiki retenu : {0} (Score: {1}%)",
            "err": "[Fandom] Erreur : {0}",
            "volume_index_err": "[Fandom] Index des tomes : {0}",
            "covers_err": "[Covers] Erreur Fandom : {0}",
        },
        "en": {
            "display_name": "Fandom (Wikis)",
            "direct_url": "[Fandom] URL / id: '{0}'",
            "search_title": "[Fandom] Looking up wiki for: '{0}'",
            "no_match": "⚠️ [Fandom] No relevant wiki for '{0}' (best score: {1}%)",
            "matched": "🎯 [Fandom] Selected wiki: {0} (Score: {1}%)",
            "err": "[Fandom] Error: {0}",
            "volume_index_err": "[Fandom] Volume index: {0}",
            "covers_err": "[Covers] Fandom error: {0}",
        },
    }

    def _headers(self) -> Dict[str, str]:
        return {"Accept": "application/json"}

    def _prefer_en(self) -> bool:
        """Toujours la rangée US/EN : le wiki EN est la source, MetaKavita traduit."""
        return True

    def extract_id_from_url(self, url: str) -> Optional[str]:
        ref = parse_fandom_url(url) or parse_fandom_token(url)
        return ref.token() if ref else None

    def _hint_ref(self, series_id: Optional[str], existing_metadata: Optional[Dict[str, Any]]) -> Optional[FandomRef]:
        meta = existing_metadata or {}
        candidates = [
            series_id,
            meta.get("fandom_url"),
            meta.get("url"),
            meta.get("webLinks"),
            meta.get("weblinks"),
        ]
        for raw in candidates:
            if not raw:
                continue
            for part in str(raw).split(","):
                ref = parse_fandom_url(part.strip()) or parse_fandom_token(part.strip())
                if ref:
                    return to_en_wiki(ref)
        return None

    def _session(self):
        return requests.Session(impersonate="chrome110")

    def _api(self, session, ref: FandomRef, params: Dict[str, Any]) -> Optional[dict]:
        query = dict(params)
        query.setdefault("format", "json")
        query.setdefault("formatversion", "2")
        try:
            res = _throttled_get(
                self,
                session,
                ref.api_url(),
                params=query,
                headers=self._headers(),
                timeout=self.http_timeout,
            )
        except Exception as exc:
            logging.debug("[Fandom] api %s: %s", ref.api_url(), exc)
            return None
        if res is None or getattr(res, "status_code", 0) != 200:
            return None
        try:
            data = res.json()
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _siteinfo(self, session, ref: FandomRef) -> Optional[dict]:
        data = self._api(
            session,
            ref,
            {"action": "query", "meta": "siteinfo", "siprop": "general"},
        )
        general = ((data or {}).get("query") or {}).get("general")
        return general if isinstance(general, dict) else None

    def _verify_wiki(self, session, ref: FandomRef, query: str) -> Optional[Tuple[FandomRef, str, float]]:
        general = self._siteinfo(session, ref)
        if not general:
            return None
        sitename = _clean_sitename(str(general.get("sitename") or ""))
        if not sitename:
            return None
        folded = _fold(sitename)
        if any(bad in folded for bad in ("fanon", "fan-fiction", "fanfiction")):
            return None
        score = calculate_similarity(query, sitename)
        if score < 0.45:
            return None
        return ref, sitename, score

    def _ddg_refs(self, session, query: str) -> List[FandomRef]:
        slugs = set(series_name_to_slugs(query))
        q = f"{query} site:fandom.com"
        html = ""
        for url, selector in (
            ("https://html.duckduckgo.com/html/", "a.result__a, a.result__url"),
            ("https://lite.duckduckgo.com/lite/", "a"),
        ):
            try:
                res = _throttled_get(
                    self,
                    session,
                    url,
                    params={"q": q},
                    headers={"Accept": "text/html"},
                    timeout=self.http_timeout,
                )
            except Exception as exc:
                logging.debug("[Fandom] ddg %s: %s", url, exc)
                continue
            if res is None or getattr(res, "status_code", 0) != 200:
                continue
            html = res.text or ""
            soup = BeautifulSoup(html, "html.parser")
            scored: List[Tuple[int, FandomRef]] = []
            for anchor in soup.select(selector):
                href = unwrap_ddg_href(anchor.get("href") or "")
                ref = parse_fandom_url(href)
                if not ref:
                    continue
                ref = to_en_wiki(ref)
                points = score_ddg_ref(query, ref, slugs)
                if points < 0:
                    continue
                scored.append((points, ref))
            if not scored:
                continue
            scored.sort(key=lambda item: item[0], reverse=True)
            seen = set()
            out: List[FandomRef] = []
            for _points, ref in scored:
                key = (ref.wiki, ref.lang, ref.page)
                if key in seen:
                    continue
                seen.add(key)
                out.append(ref)
                if len(out) >= 4:
                    break
            if out:
                return out
        return []

    def _resolve_ref(
        self,
        session,
        query: str,
        series_id: Optional[str],
        existing_metadata: Optional[Dict[str, Any]],
    ) -> Optional[FandomRef]:
        """Même ancrage que l'index des tomes : un wiki qui répond, pas un slug mort."""
        hinted = self._hint_ref(series_id, existing_metadata)
        if hinted:
            if self._siteinfo(session, hinted) or series_id:
                return hinted

        slugs = series_name_to_slugs(query)
        curated = set(wiki_alias_slugs(query))
        for i, slug in enumerate(slugs):
            ref = FandomRef(wiki=slug)
            if i < 2 or slug in curated:
                if self._siteinfo(session, ref):
                    return ref
                continue
            checked = self._verify_wiki(session, ref, query)
            if checked:
                return checked[0]
        for ref in self._ddg_refs(session, query):
            ref = to_en_wiki(ref)
            if self._siteinfo(session, ref):
                return ref
        return None

    def _stamp_index(
        self, index: Dict[str, Dict[str, str]], ref: FandomRef, page: str
    ) -> Dict[str, Dict[str, str]]:
        page_url = ref.page_url(page)
        for number, payload in index.items():
            payload.setdefault("provider_ref", f"{page_url}#Volume_{number}")
        return index

    def _pageprops_descriptions(
        self, session, ref: FandomRef, titles: List[str]
    ) -> Dict[str, str]:
        """`fandomdescription` de plusieurs fiches tome, 50 titres par requête."""
        unique: List[str] = []
        seen = set()
        for title in titles:
            key = (title or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(key)
        out: Dict[str, str] = {}
        for start in range(0, len(unique), PAGEPROPS_BATCH):
            chunk = unique[start : start + PAGEPROPS_BATCH]
            data = self._api(
                session,
                ref,
                {
                    "action": "query",
                    "prop": "pageprops",
                    "ppprop": "fandomdescription",
                    "redirects": 1,
                    "titles": "|".join(chunk),
                },
            )
            query = (data or {}).get("query") or {}
            for page in query.get("pages") or []:
                if not isinstance(page, dict) or page.get("missing"):
                    continue
                title = (page.get("title") or "").strip()
                desc = clean_summary(
                    ((page.get("pageprops") or {}).get("fandomdescription") or "")
                )
                if title and desc:
                    out[title] = desc
            for redir in query.get("redirects") or []:
                if not isinstance(redir, dict):
                    continue
                dest = out.get((redir.get("to") or "").strip())
                src = (redir.get("from") or "").strip()
                if dest and src:
                    out[src] = dest
        return out

    def _apply_summaries(self, session, ref: FandomRef, index: Dict[str, Dict[str, str]]) -> None:
        wanted = []
        for number, payload in index.items():
            page = (payload.get("_page") or "").strip() or f"Volume {number}"
            payload["_page"] = page
            wanted.append(page)
        descriptions = self._pageprops_descriptions(session, ref, wanted)
        for _number, payload in index.items():
            page = payload.pop("_page", "")
            chapters = payload.pop("_chapters", "")
            extra = payload.pop("_extra", "")
            explicit = payload.pop("summary", "")
            desc = descriptions.get(page) or ""
            plot = ""
            cover = ""
            if desc and is_cover_blurb(desc):
                cover = desc
            elif desc:
                plot = desc
            if explicit:
                if is_cover_blurb(explicit):
                    cover = cover or explicit
                else:
                    plot = plot or explicit
            chosen = pick_summary(plot=plot, chapters=chapters, cover=cover, extra=extra)
            if chosen:
                payload["summary"] = chosen

    def _volume_page_titles(self, session, ref: FandomRef) -> List[str]:
        titles: List[str] = []
        seen = set()
        for prefix in ("Volume", "Manga Volume"):
            data = self._api(
                session,
                ref,
                {
                    "action": "query",
                    "list": "allpages",
                    "apprefix": prefix,
                    "apnamespace": 0,
                    "aplimit": min(self.VOLUME_INDEX_MAX, 200),
                },
            )
            for page in ((data or {}).get("query") or {}).get("allpages") or []:
                title = (page.get("title") or "").strip()
                if not title or title in seen or not is_indexable_volume_page(title):
                    continue
                seen.add(title)
                titles.append(title)
        return titles

    def _index_from_volume_pages(self, session, ref: FandomRef) -> Optional[Dict[str, Any]]:
        """Wikis sans page liste : `Volume 1`…`Volume N` en lots de 50."""
        titles = self._volume_page_titles(session, ref)
        if not titles:
            return None
        index: Dict[str, Dict[str, str]] = {}
        prefer_en = self._prefer_en()
        for start in range(0, len(titles), PAGEPROPS_BATCH):
            chunk = titles[start : start + PAGEPROPS_BATCH]
            data = self._api(
                session,
                ref,
                {
                    "action": "query",
                    "prop": "revisions|pageimages",
                    "rvprop": "content",
                    "rvslots": "main",
                    "piprop": "thumbnail",
                    "pithumbsize": 400,
                    "redirects": 1,
                    "titles": "|".join(chunk),
                },
            )
            for page in ((data or {}).get("query") or {}).get("pages") or []:
                if not isinstance(page, dict) or page.get("missing"):
                    continue
                title = (page.get("title") or "").strip()
                number = volume_number_from_title(title)
                if not number:
                    continue
                if number in index and not _VOLUME_HEAD.match(title):
                    continue
                revs = page.get("revisions") or []
                slot = ((revs[0] or {}).get("slots") or {}).get("main") or {}
                wikitext = slot.get("content") or (revs[0] or {}).get("content") or ""
                payload = parse_volume_page_wikitext(
                    str(wikitext), fallback_number=number, prefer_en=prefer_en
                )
                thumb = ((page.get("thumbnail") or {}).get("source") or "")
                cover = upgrade_cover(thumb)
                if cover:
                    payload["cover_url"] = cover
                payload["_page"] = title
                if payload:
                    index[number] = payload
        if not index:
            return None
        self._apply_summaries(session, ref, index)
        return self._stamp_index(_public_index(index), ref, "Volume 1")

    def _existing_titles(self, session, ref: FandomRef, titles: List[str]) -> List[str]:
        """Les titres de `titles` qui existent, dans le même ordre (une requête)."""
        wanted = [title for title in titles if title]
        if not wanted:
            return []
        data = self._api(
            session,
            ref,
            {"action": "query", "titles": "|".join(wanted), "redirects": 1},
        )
        query = (data or {}).get("query") or {}
        present = set()
        for page in query.get("pages") or []:
            if isinstance(page, dict) and not page.get("missing"):
                present.add((page.get("title") or "").strip())
        aliases = {}
        for item in query.get("redirects") or []:
            if isinstance(item, dict):
                aliases[(item.get("from") or "").strip()] = (item.get("to") or "").strip()
        out: List[str] = []
        for title in wanted:
            dest = aliases.get(title, title)
            if dest in present or title in present:
                out.append(title)
        return out

    def _index_from_ref(self, session, ref: FandomRef) -> Optional[Dict[str, Any]]:
        """Page liste d'abord ; sinon les fiches `Volume N` du wiki."""
        ref = to_en_wiki(ref)
        pages = pages_to_parse(ref)
        first = pages[0] if pages else ""
        candidates = [first] if first else []
        if first:
            html, wikitext = self._parse_page(session, ref, first)
            index = self._index_from_page(html, wikitext)
            if index:
                return self._finish_index(session, ref, index, first)
            candidates = self._existing_titles(session, ref, pages[1:])
        for page in candidates:
            html, wikitext = self._parse_page(session, ref, page)
            index = self._index_from_page(html, wikitext)
            if index:
                return self._finish_index(session, ref, index, page)
        return self._index_from_volume_pages(session, ref)

    def _finish_index(
        self, session, ref: FandomRef, index: Dict[str, Dict[str, str]], page: str
    ) -> Dict[str, Any]:
        self._apply_summaries(session, ref, index)
        public = _public_index(index)
        if index_missing_bibliography(public):
            extra = self._index_from_volume_pages(session, ref)
            if extra:
                public = merge_volume_payloads(public, extra)
        return self._stamp_index(public, ref, page)

    def _parse_page(self, session, ref: FandomRef, page: str) -> Tuple[str, str]:
        data = self._api(
            session,
            ref,
            {
                "action": "parse",
                "page": page,
                "prop": "text|wikitext",
                "redirects": 1,
            },
        )
        parsed = (data or {}).get("parse") or {}
        html = parsed.get("text") or ""
        wikitext = parsed.get("wikitext") or ""
        if isinstance(html, dict):
            html = html.get("*") or ""
        if isinstance(wikitext, dict):
            wikitext = wikitext.get("*") or ""
        return str(html), str(wikitext)

    def _index_from_page(self, html: str, wikitext: str) -> Dict[str, Dict[str, str]]:
        prefer_en = self._prefer_en()
        html_index = parse_html_volumes(html, prefer_en=prefer_en)
        wiki_index = parse_wikitext_volumes(wikitext, prefer_en=prefer_en)
        merged = merge_volume_payloads(wiki_index, html_index)
        if len(merged) > self.VOLUME_INDEX_MAX:
            keys = sorted(merged, key=lambda k: float(k) if k.replace(".", "", 1).isdigit() else 0)
            merged = {k: merged[k] for k in keys[: self.VOLUME_INDEX_MAX]}
        return merged

    def fetch(
        self,
        query: str,
        library_type: str = "Manga",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        cleaned = clean_title(query, library_type=library_type) or (query or "").strip()
        if not cleaned:
            return None
        session = self._session()
        try:
            raw = query.strip() if is_id else ""
            ref = self._resolve_ref(session, cleaned, raw or None, existing_metadata)
            if not ref:
                logging.info(self.t("no_match").format(cleaned, 0))
                return None
            general = self._siteinfo(session, ref) or {}
            sitename = _clean_sitename(str(general.get("sitename") or ""))
            if not sitename and not is_id:
                logging.info(self.t("no_match").format(cleaned, 0))
                return None
            sitename = sitename or cleaned
            fmt = {"Manga": "manga", "Comic": "comic", "Book": "book"}.get(library_type, "manga")
            alts = series_alt_titles(cleaned, sitename, ref.wiki)
            candidate = {
                "title": sitename,
                "url": ref.page_url() if ref.page else f"https://{ref.wiki}.fandom.com/",
                "format": fmt,
            }
            if alts:
                candidate["alternative_titles"] = alts
            if is_id:
                logging.info(self.t("direct_url").format(ref.token()))
                return attach_match_score(candidate, 1.0)
            score = score_candidate(candidate, cleaned, existing_metadata)
            if score < get_match_accept_threshold():
                logging.info(self.t("no_match").format(cleaned, int(score * 100)))
                return None
            logging.info(self.t("matched").format(sitename, int(score * 100)))
            return attach_match_score(candidate, score)
        except Exception as exc:
            logging.error(self.t("err").format(exc))
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    def fetch_volume_index(
        self,
        query: str,
        library_type: str = "Comic",
        series_id: Optional[str] = None,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        cleaned = clean_title(query, library_type=library_type) or (query or "").strip()
        if not cleaned and not series_id:
            return None
        session = self._session()
        try:
            hinted = self._hint_ref(series_id, existing_metadata)
            if hinted:
                return self._index_from_ref(session, hinted)

            slugs = series_name_to_slugs(cleaned or query)
            curated = set(wiki_alias_slugs(cleaned or query))
            for i, slug in enumerate(slugs):
                ref = FandomRef(wiki=slug)
                if i < 2 or slug in curated:
                    if not self._siteinfo(session, ref):
                        continue
                elif not self._verify_wiki(session, ref, cleaned or query):
                    continue
                index = self._index_from_ref(session, ref)
                if index:
                    return index
            for ref in self._ddg_refs(session, cleaned or query):
                index = self._index_from_ref(session, ref)
                if index:
                    return index
            return None
        except Exception as exc:
            logging.error(self.t("volume_index_err").format(exc))
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    def fetch_covers(self, query: str, library_type: str = "Manga") -> List[Dict[str, str]]:
        # Les jaquettes voyagent avec `fetch_volume_index`. Relancer l'index
        # ici doublerait une cascade déjà lente (4–8 s par requête).
        return []
