# BnF Catalogue

| | |
|---|---|
| **ID** | `BNF` |
| **File** | [`bnf.py`](../../bnf.py) |
| **Types** | Book |
| **Method** | SRU (catalog) |
| **Status** | Stable |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 99 |
| **Auth** | None |
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://catalogue.bnf.fr |

## Summary

BnF catalogue — SRU Dublin Core (no native covers).

## Quality / when to pick

French national catalog — no covers (pair with Babelio/Decitre).

Gaps: `provider: cover_url; opt.: publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`bnf.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bnf.py) into `data/scrapers/`.
2. Verify SHA-256: `709bc1308ebbbe393228e89f93451a9310fdd5fcb237731d87edb2da3e32ba31`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key.

## Proxy domains (covers)

`bnf.fr`, `catalogue.bnf.fr`

## Warnings

_None._

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BNF`.
