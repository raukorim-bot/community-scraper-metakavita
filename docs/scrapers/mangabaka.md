# MangaBaka (API / Rapide)

| | |
|---|---|
| **ID** | `MANGABAKA` |
| **File** | [`mangabaka.py`](../../mangabaka.py) |
| **Types** | Book, Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `2.25` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, ja |
| **Site** | https://mangabaka.org |
| **Version** | `1.1.0` |

## Summary

MangaBaka — v2 API (manga / novels). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`mangabaka.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mangabaka.py) into `data/scrapers/`.
2. Verify SHA-256: `069152099d8fbdb49680aa4ee662739f84b5020a91d1b6f2db8510ba2de92f1f`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`mangabaka.org`, `api.mangabaka.org`, `images.mangabaka.org`, `cdn.mangabaka.org`, `mangabaka.dev`, `api.mangabaka.dev`, `images.mangabaka.dev`, `cdn.mangabaka.dev`

## Warnings

- Search endpoint 30 req/min; rate_limit=2.25 keeps ~10% headroom.
- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGABAKA`.
