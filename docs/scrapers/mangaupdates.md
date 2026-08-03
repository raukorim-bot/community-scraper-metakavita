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
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.mangaupdates.com |

## Summary

MangaUpdates (Baka-Updates) — API. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`mangaupdates.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mangaupdates.py) into `data/scrapers/`.
2. Verify SHA-256: `e72e93b3a05d665327c72aadf73a857fecf1df42e2873e7546f8852deb6e4c14`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`mangaupdates.com`, `api.mangaupdates.com`, `www.mangaupdates.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGAUPDATES`.
