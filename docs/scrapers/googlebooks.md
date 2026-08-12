# Google Books

| | |
|---|---|
| **ID** | `GOOGLEBOOKS` |
| **File** | [`googlebooks.py`](../../googlebooks.py) |
| **Types** | Book, Comic |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `GOOGLEBOOKS_API_KEY` |
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, fr |
| **Site** | https://books.google.com |
| **Version** | `1.0.0` |

## Summary

Google Books — books / comics (API). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`googlebooks.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/googlebooks.py) into `data/scrapers/`.
2. Verify SHA-256: `fd0323e60f4ad59e72bac820d94d5bfe7790c48f40dcb39f977e95bffe30b4b9`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic).

### Setup

Google key → GOOGLEBOOKS_API_KEY. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`books.google.com`, `books.googleusercontent.com`, `googleusercontent.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `GOOGLEBOOKS`.
