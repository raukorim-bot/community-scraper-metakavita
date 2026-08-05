# Shikimori (API JSON)

| | |
|---|---|
| **ID** | `SHIKIMORI` |
| **File** | [`shikimori.py`](../../shikimori.py) |
| **Types** | Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `0.75` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | RU — ru, en, ja |
| **Site** | https://shikimori.one |

## Summary

Shikimori — manga JSON API. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`shikimori.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/shikimori.py) into `data/scrapers/`.
2. Verify SHA-256: `2893e14230d7193cc271f6ff1596abf009c82b1b12f4caa64998f583f45346c1`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`shikimori.one`, `shikimori.me`

## Warnings

- Official limit 5 rps and 90 rpm; rate_limit=0.75 stays ~10% under rpm.

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `SHIKIMORI`.
