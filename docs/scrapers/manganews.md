# Manga-News (Catalogue VF)

| | |
|---|---|
| **ID** | `MANGANEWS` |
| **File** | [`manganews.py`](../../manganews.py) |
| **Types** | Manga |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.manga-news.com |

## Summary

Manga-News — French catalog. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`manganews.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/manganews.py) into `data/scrapers/`.
2. Verify SHA-256: `0a4562bcbb60009cf11419ac887ea3600ebeb76348344f314309df470234c57a`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`manga-news.com`, `www.manga-news.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGANEWS`.
