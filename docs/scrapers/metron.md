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
| **Rate limit** | `3.4` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://metron.cloud |
| **Version** | `1.0.0` |

## Summary

Metron comics API (series, issues, covers). API key required.

## Quality / when to pick

Best comics API (key) — staff from 1st issue + covers.

Gaps: `opt.: isbn, alternative_titles` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`metron.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/metron.py) into `data/scrapers/`.
2. Verify SHA-256: `6e044cf161b034ec9adeea4dd86c63365e75cc3a9596c6e7ce5915b819fbaf66`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

metron.cloud account → API Tokens → METRON_API_KEY (Bearer, or user:password).

## Proxy domains (covers)

`metron.cloud`, `static.metron.cloud`

## Warnings

- Quota API Metron (~20 req/min) — rate_limit=3.4 (marge 10%).

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `METRON`.
