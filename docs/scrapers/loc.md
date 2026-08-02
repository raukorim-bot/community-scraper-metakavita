# Library of Congress

| | |
|---|---|
| **ID** | `LOC` |
| **File** | [`loc.py`](../../loc.py) |
| **Types** | Book |
| **Method** | SRU (catalog) |
| **Status** | Stable |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 97 |
| **Auth** | None |
| **Rate limit** | `1.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.loc.gov |

## Summary

Library of Congress — LCDB SRU (Dublin Core). Covers rarely available.

## Quality / when to pick

Library of Congress — SRU DC, covers/URL rarely present.

Gaps: `provider: cover_url, summary, url; opt.: isbn, publisher, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`loc.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/loc.py) into `data/scrapers/`.
2. Verify SHA-256: `c7a4d0e033a56e0e23d441503ded7272834e71cb0861bc9c706a295d7f25da16`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. rate_limit=1.5 s. JSON loc.gov fallback if SRU empty.

## Proxy domains (covers)

`loc.gov`, `www.loc.gov`, `tile.loc.gov`, `cover.loc.gov`

## Warnings

- Couvertures absentes via SRU DC.
- Préférer une requête avec auteur pour de meilleures notices.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `LOC`.
