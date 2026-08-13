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
| **Rate limit** | `0.4` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | JP — ja |
| **Site** | https://www.openbd.jp |
| **Version** | `1.1.0` |

## Summary

openBD — JP bibliography / covers by ISBN (free API). No title search.

## Quality / when to pick

JP ISBN + covers — summary often missing.

Gaps: `provider: summary; opt.: tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`openbd.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/openbd.py) into `data/scrapers/`.
2. Verify SHA-256: `d709f15920eb4e01f0fe438aa921c20a90d1f7bc376513cecfb121401d5ab22c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. ISBN required (query or existing metadata).

## Proxy domains (covers)

`openbd.jp`, `api.openbd.jp`, `cover.openbd.jp`, `www.openbd.jp`

## Warnings

- openBD has no hard rate limit (bulk-oriented); 0.4 s is polite.
- API ISBN-only — couplez avec NDL pour la recherche titre.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `OPENBD`.
