# Manga-Sanctuary

| | |
|---|---|
| **ID** | `MANGASANCTUARY` |
| **File** | [`mangasanctuary.py`](../../mangasanctuary.py) |
| **Types** | Manga |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.manga-sanctuary.com |
| **Version** | `1.1.0` |

## Summary

Manga-Sanctuary — French manga catalog (HTML).

## Quality / when to pick

French manga site — covers OK.

Gaps: `opt.: isbn, publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`mangasanctuary.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mangasanctuary.py) into `data/scrapers/`.
2. Verify SHA-256: `ec22ae8cf253849ef66c9abcf75757c5b12b8c688f5bf6a94afe362dc2e32c7a`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. rate_limit=2.5 s.

## Proxy domains (covers)

`manga-sanctuary.com`, `www.manga-sanctuary.com`

## Warnings

- Site HTML — anti-ban rate limit.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGASANCTUARY`.
