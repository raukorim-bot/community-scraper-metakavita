# Changelog — community-scraper-metakavita

## [2026-08-05] Rate limits + Anime-Planet covers

### Rate limits (safe margins)

Audit of published / polite ceilings; `rate_limit` set ~5–10% under the documented cap where known. Catalog + per-scraper docs updated; core mirrors stay in sync via `is_core` sha.

| ID | New `rate_limit` | Notes |
|---|---|---|
| ANILIST | 2.25 | Degraded API cap ~30/min (−10%) until AniList restores normal |
| SHIKIMORI | 0.75 | ~90 rpm (−10%) |
| LOC | 3.4 | loc.gov JSON 20/min (−10%) |
| LOCG | 5.0 | Interactive use; robots Crawl-delay 30 is for search bots — prefer ComicVine/Metron for bulk |
| MANGANEWS | 2.5 | HTML polite |
| BDTHEQUE | 2.2 | HTML polite |
| METRON | 3.4 | 20/min (−10%) |
| MANGABAKA | 2.25 | Search 30/min (−10%) |
| ISBNDB | 1.1 | Basic plan ~1/s (−10%) |
| MANGADEX | 0.25 | ~5 req/s (−10%) |
| OPENBD | 0.4 | No hard public limit |
| MANGAUPDATES | 0.55 | Mostly free reads + DDoS cushion |
| OPENLIBRARY | 1.1 | Anonymous ~1/s |
| ANN | 1.1 | Official 1/s (−10%) |

### Bug fixes

* **Anime-Planet `1.0.1` — manual cover picker** — `fetch_covers` now prefers detail `og:image` (full JPEG) over tiny search thumbs, upgrades `-WxH.webp` CDN URLs, and sorts search hits by title relevance (`average` search + exact/prefix ranking). Catalog sha updated.

### Tooling

* `scripts/verify_core_mirror.py` — helper to check community ↔ MetaKavita core rate_limit / sha alignment.
