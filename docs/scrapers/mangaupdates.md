# MangaUpdates (Baka-Updates)

| | |
|---|---|
| **ID** | `MANGAUPDATES` |
| **File** | [`mangaupdates.py`](../../mangaupdates.py) |
| **Types** | Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `0.55` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.mangaupdates.com |
| **Version** | `1.1.0` |

## Summary

MangaUpdates (Baka-Updates) — API. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`mangaupdates.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mangaupdates.py) into `data/scrapers/`.
2. Verify SHA-256: `63ec1394b8b3e76b2175db20728d91c536248ef0181155563dc7e5d9b55d7526`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`mangaupdates.com`, `api.mangaupdates.com`, `www.mangaupdates.com`

## Warnings

- Reads mostly unlimited; 0.55 s cushions DDoS 429 protection.
- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGAUPDATES`.
