# Tapas

| | |
|---|---|
| **ID** | `TAPAS` |
| **File** | [`tapas.py`](../../tapas.py) |
| **Types** | Manga |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 98 |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://tapas.io |

## Summary

Tapas — webcomics / manhwa (HTML).

## Quality / when to pick

Manhwa/webcomics — covers OK; public HTML lacks summary/year.

Gaps: `provider: summary, year; opt.: isbn, publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`tapas.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/tapas.py) into `data/scrapers/`.
2. Verify SHA-256: `1d5f73b733ba34d0970c5c0cf6e490a8432dd9f2512ee5367c52398bbaadcfe0`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. rate_limit=2.5 s.

## Proxy domains (covers)

`tapas.io`, `www.tapas.io`, `us-a.tapas.io`, `s3.tapasticusercontent.com`, `tapas-prod.s3.amazonaws.com`

## Warnings

- Site HTML — anti-ban rate limit.
- Synopsis série rarement exposé en HTML public (pitch marketing og:description).

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `TAPAS`.
