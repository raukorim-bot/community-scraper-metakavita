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
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://isbndb.com |

## Summary

ISBNdb — books REST API (paid plan). Not live-tested in this repo.

## Quality / when to pick

Worldwide ISBN — paid key required, not live-tested.

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`isbndb.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/isbndb.py) into `data/scrapers/`.
2. Verify SHA-256: `55d8176285b3527ba82cc85aa2737ee18e81101d2f40629079ff688d73680ada`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

Paid REST key → ISBNDB_API_KEY.

## Proxy domains (covers)

`isbndb.com`, `api2.isbndb.com`, `images.isbndb.com`

## Warnings

- Abonnement payant requis.
- Non validé en live (pas de clé de test).

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ISBNDB`.
