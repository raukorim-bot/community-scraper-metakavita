# Metron (Comics API)

| | |
|---|---|
| **ID** | `METRON` |
| **File** | [`metron.py`](../../metron.py) |
| **Types** | Comic |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | Required — `METRON_API_KEY` (Bearer or `user:password`) |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://metron.cloud |

## Summary

Metron comics API (series, issues, covers). API key required.

## Quality / when to pick

Best comics API (key) — staff from 1st issue + covers.

Gaps: `opt.: isbn, alternative_titles` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`metron.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/metron.py) into `data/scrapers/`.
2. Verify SHA-256: `576ce6840092849f8b6c75b3ebb26b563d3cd7a908b7e8397feff6ab336366e3`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

metron.cloud account → API Tokens → METRON_API_KEY (Bearer, or user:password).

## Proxy domains (covers)

`metron.cloud`, `static.metron.cloud`

## Warnings

- Quota API Metron (~20 req/min) — rate_limit=3.0.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `METRON`.
