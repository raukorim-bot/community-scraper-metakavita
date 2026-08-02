# openBD (JP)

| | |
|---|---|
| **ID** | `OPENBD` |
| **File** | [`openbd.py`](../../openbd.py) |
| **Types** | Book |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 99 |
| **Auth** | None |
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | JP — ja |
| **Site** | https://www.openbd.jp |

## Summary

openBD — JP bibliography / covers by ISBN (free API). No title search.

## Quality / when to pick

JP ISBN + covers — summary often missing.

Gaps: `provider: summary; opt.: tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`openbd.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/openbd.py) into `data/scrapers/`.
2. Verify SHA-256: `86b132b69e2e8c483ac438af852a6846be29c75647db513a8c3cfa3429a2aba9`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. ISBN required (query or existing metadata).

## Proxy domains (covers)

`openbd.jp`, `api.openbd.jp`, `cover.openbd.jp`, `www.openbd.jp`

## Warnings

- API ISBN-only — couplez avec NDL pour la recherche titre.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `OPENBD`.
