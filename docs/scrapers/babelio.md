# Babelio (Littérature FR)

| | |
|---|---|
| **ID** | `BABELIO` |
| **File** | [`babelio.py`](../../babelio.py) |
| **Types** | Book |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.babelio.com |

## Summary

French literature catalog (reviews, summary, cover). HTML scraping.

## Quality / when to pick

French literature — best for FR Book libraries.

Gaps: `opt.: alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`babelio.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/babelio.py) into `data/scrapers/`.
2. Verify SHA-256: `6e0a24358254889c469132b62e75035a0c71f1cc0def6808a8bfc88537c6b89c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. rate_limit=3.0 s recommended.

## Proxy domains (covers)

`babelio.com`, `www.babelio.com`, `images-na.ssl-images-amazon.com`, `images-eu.ssl-images-amazon.com`, `ecx.images-amazon.com`, `m.media-amazon.com`

## Warnings

- Site HTML — respecter le rate limit pour éviter un ban IP.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BABELIO`.
