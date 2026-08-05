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
| **Rate limit** | `0.25` s |
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
2. Verify SHA-256: `e5cae15372e7a81b1eb5fac236f5de7f10b2addeb90d1859781440e4b3eabe92`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`mangadex.org`, `uploads.mangadex.org`, `api.mangadex.org`

## Warnings

- MangaDex global ~5 req/s; rate_limit=0.25 keeps ~10% headroom.

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGADEX`.
