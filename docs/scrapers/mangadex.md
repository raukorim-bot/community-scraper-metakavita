# MangaDex (API)

| | |
|---|---|
| **ID** | `MANGADEX` |
| **File** | [`mangadex.py`](../../mangadex.py) |
| **Types** | Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `0.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, ja |
| **Site** | https://mangadex.org |

## Summary

MangaDex — public API. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`mangadex.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mangadex.py) into `data/scrapers/`.
2. Verify SHA-256: `4a48c35713f29b9f868248b0f6e2e0abc7226eb0d43fd799a4a682aaf704a8ec`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`mangadex.org`, `uploads.mangadex.org`, `api.mangadex.org`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGADEX`.
