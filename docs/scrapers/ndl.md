# NDL Search (JP)

| | |
|---|---|
| **ID** | `NDL` |
| **File** | [`ndl.py`](../../ndl.py) |
| **Types** | Book |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 99 |
| **Auth** | None |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | JP — ja, en |
| **Site** | https://ndlsearch.ndl.go.jp |
| **Version** | `1.0.0` |

## Summary

NDL Search — National Diet Library of Japan (OpenSearch).

## Quality / when to pick

JP national library — records, no covers (see openBD).

Gaps: `provider: cover_url; opt.: tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`ndl.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/ndl.py) into `data/scrapers/`.
2. Verify SHA-256: `c7c5d1ebf38157af1ae623300e8f02535265dcaba52d7823009a522fa4dc751c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. No reliable native covers (use openBD for ISBNs).

## Proxy domains (covers)

`ndl.go.jp`, `ndlsearch.ndl.go.jp`, `dl.ndl.go.jp`, `www.ndl.go.jp`

## Warnings

_None._

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `NDL`.
