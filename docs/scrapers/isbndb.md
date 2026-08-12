# ISBNdb

| | |
|---|---|
| **ID** | `ISBNDB` |
| **File** | [`isbndb.py`](../../isbndb.py) |
| **Types** | Book |
| **Method** | Official API |
| **Status** | Not live-tested |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `ISBNDB_API_KEY` |
| **Rate limit** | `1.1` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://isbndb.com |
| **Version** | `1.0.0` |

## Summary

ISBNdb — books REST API (paid plan). Not live-tested in this repo.

## Quality / when to pick

Worldwide ISBN — paid key required, not live-tested.

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`isbndb.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/isbndb.py) into `data/scrapers/`.
2. Verify SHA-256: `27a66c770cfb9ac8ba62752aa6af3f0b02c1c4fa56602dc2ec0d1703a9e79bd8`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

Paid REST key → ISBNDB_API_KEY.

## Proxy domains (covers)

`isbndb.com`, `api2.isbndb.com`, `images.isbndb.com`

## Warnings

- Basic plan 1 req/s; rate_limit=1.1 keeps ~10% headroom.
- Abonnement payant requis.
- Non validé en live (pas de clé de test).

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ISBNDB`.
