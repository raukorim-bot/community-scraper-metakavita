# Changelog — community-scraper-metakavita

## [Unreleased] `BDGEST` retired — one scraper per host

`BDGEST` is **retired**, replaced by `BEDETHEQUE` (shipped as MetaKavita core).

### Why

Its own search (`bdgest.com/search`) has been dead for a while; the scraper queried
**bedetheque.com** end to end — the same site as `BEDETHEQUE`, which handles it better:
CSRF token, ban `403` told apart from a missing-page `404`, ISO-8859-1 decoding, album index.

The decisive reason is not the duplication but the throttling. `throttle_provider()` is keyed
on the **scraper id**, so `BDGEST` and `BEDETHEQUE` kept two independent clocks for a single
host: a user who enabled both hit bedetheque.com at the sum of the two rates. That is the same
traffic pattern as the burst bug fixed below, reached by a different route — and bedetheque.com
banned an IP over it. Per-scraper throttling is deliberate and stays; the fix is to ship one
scraper per host.

### Retired, not deleted

The entry stays in `store/catalog.json` with `retired: true` / `lifecycle: "retired"` /
`status: "retired"` / a `retired` tag — the four signals `services/scraper_store.is_entry_retired`
accepts. MetaKavita then refuses the install (HTTP 403) and badges the provider **Out of service**
for users who already have `data/scrapers/bdgest.py`. Deleting the entry would only downgrade that
to a generic *Removed from store* badge with no reason attached, so the file would sit there
unexplained. `bdgest.py` therefore stays in the repo too: `verify_catalog_sha.py` reads the `.py`
of every catalog entry, and the entry has to outlive the scraper.

The file keeps its `1.1.0` throttle fix but no one will receive it — a retired entry cannot be
installed or updated. The remedy for an installed copy is removal, not an update.

### Changed

* `store/meta.json`, `store/quality.json`, `store/catalog.json` — `BDGEST` marked retired, with
  the reason and the replacement (`retirement.reason.fr` / `.en`).
* `scripts/build_store_catalog.py` — reads the retirement block from `meta.json`, emits the four
  signals plus the `retired` tag, and generates a doc page that carries a *do not install* banner
  and removal steps instead of install steps.
* `tests/test_bdgest_retired.py` — offline guard: the entry must exist **and** be retired, in
  `meta.json` and in `catalog.json`, and must not come back as installable.
* `tests/run_quality.py`, `tests/run_live_smoke.py` — `BDGEST` cases dropped, so a maintainer run
  no longer hits bedetheque.com twice.

## [Unreleased] Per-request rate limiting (IP-ban fix)

### Why

A scraper's `rate_limit` was applied **once per `fetch()`**, by the caller, before the call.
The 4–14 requests issued *inside* `fetch()` escaped it entirely and went out as a burst —
the traffic pattern that gets an IP banned on sites without an API. This actually happened
on bedetheque.com, which `bdgest.py` targets.

MetaKavita added `BaseScraper._http_get` / `_http_post`, which call `throttle_provider()`
before every request. All 19 non-core catalog scrapers now route through it.

### Compatibility

A catalog scraper can be installed on a MetaKavita image older than that helper, where
calling it would raise `AttributeError` at runtime. Each converted file therefore carries a
self-contained `_throttled_get` (`_throttled_post` where needed) that probes
`getattr(self, "_http_get", None)` and, when absent, falls back to `throttle_provider()`
directly — and to a module-local monotonic counter if even that module is missing. No path
can emit an unthrottled request.

### Scrapers bumped to `1.1.0`

`ANIMEPLANET`, `BANGUMI`, `BDGEST`, `BNE`, `BNF`, `DNB`, `GCD`, `ISBNDB`, `KB`, `LOC`,
`MANGASANCTUARY`, `NDL`, `NOVELUPDATES`, `OPENBD`, `SBN`, `TAPAS`, `TEBEOSFERA`, `WEBTOON`,
`WIKIDATA`.

`WIKIDATA` already paced every request, but on a private per-instance clock invisible to the
rest of the app; it now joins the shared one.

### Tooling / tests

* `tests/test_scrapers_are_throttled.py` — offline AST guard: no community scraper may issue
  a raw outgoing request, every HTTP helper must probe `_http_get` via `getattr`, and every
  scraper that makes requests must declare a class-level `version`.
* `tests/test_throttle_compat.py` — fake clock + fake session: proves the throttled path is
  taken once per request when the helper exists, and that the fallback paces when it does not.
* `scripts/sync_core_from_metakavita.py` — the seven `EXISTING_CORE` mirrors were only tagged
  `is_core`, never re-copied, so their catalog copy had silently drifted behind the image.
  They are now refreshed like the rest.

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
