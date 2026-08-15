# Fandom (Wikis)

| | |
|---|---|
| **ID** | `FANDOM` |
| **File** | [`fandom.py`](../../fandom.py) |
| **Types** | Book, Comic, Manga |
| **Method** | Official API |
| **Status** | Beta |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `6.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | Global — en |
| **Site** | https://www.fandom.com |
| **Version** | `1.4.1` |

## Summary

English Fandom wikis — series match (live wiki) + volume index. Not a primary: AniList / Manga-News first.

## Quality / when to pick

Wiki volume index — titles / summaries / dates / ISBN / covers when catalogs miss. Not a primary.

Gaps: `provider: status, tags; opt.: publisher, alternative_titles` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Covers

Volume covers come from the list-page parse or Volume N thumbnails (`static.wikia.nocookie.net`). `requires_proxy` is on. `fetch_covers` is empty on purpose so the cover picker does not re-run the whole index.

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`fandom.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/fandom.py) into `data/scrapers/`.
2. Verify SHA-256: `2d01ad51751581e6f81f3f99e42a9063e836f982814f07c6a807708bb6bd102b`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic, Manga).

### Setup

No API key. English wiki only (MetaKavita translates). Random 4–8 s pace. Requires MetaKavita ≥ 1.7.0. Keep last in the cascade, not PROVIDER_1.

## Proxy domains (covers)

`fandom.com`, `wikia.com`, `wikia.nocookie.net`, `static.wikia.nocookie.net`, `images.wikia.com`

## Warnings

- Not a single catalog — each series is its own wiki. Blind community.fandom.com search is Cloudflare-blocked.
- Volume summaries are wiki text (CC-BY-SA): plot when the wiki has one, otherwise the chapter list.
- English wiki only (localized /fr/ URLs are rewritten). A list-page parse returns every volume; wikis without one fall back to Volume N articles (allpages + revisions). Synopses are batched via pageprops.
- DuckDuckGo HTML often returns a challenge (202). Title slugs include a last-word guess and a few EN→wiki aliases (JoJo → jojo, Komi → komisan) so niche wikis still resolve.
- List-page wikitext templates (Tankobon, Volumes, Infobox:Volume) carry dates/ISBNs. Blu-ray, Episode Nagi and light-novel pages are skipped.
- Rate limit is randomized 4–8 s to reduce bans. Happy path is one parse, not one page per volume.
- Prefer Manga-News / ComicVine / Bédéthèque first. Fandom fills titles, summaries, dates, ISBNs and covers when catalogs miss.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `FANDOM`.
