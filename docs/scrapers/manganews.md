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
| **Version** | `1.1.0` |

## Summary

Manga-News — French catalog. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`manganews.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/manganews.py) into `data/scrapers/`.
2. Verify SHA-256: `869d51a1479b3ecc89ed9ea3a83c8345f13f7e64cf3871d67bb0b9aa2bc20ea0`.
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
