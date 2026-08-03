# SensCritique (FR)

| | |
|---|---|
| **ID** | `SENSCRITIQUE` |
| **File** | [`senscritique.py`](../../senscritique.py) |
| **Types** | Book, Comic |
| **Method** | GraphQL (front) |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.senscritique.com |

## Summary

Books and comics via SensCritique front-end Apollo GraphQL.

## Quality / when to pick

FR Book/Comic — GraphQL, covers OK.

Gaps: `opt.: tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`senscritique.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/senscritique.py) into `data/scrapers/`.
2. Verify SHA-256: `174e8232120354ccbff6dec9e02fc9d9f537e59f6a20f6eb5b6faca0810fed83`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic).

### Setup

No API key. rate_limit=2.5 s.

## Proxy domains (covers)

`senscritique.com`, `www.senscritique.com`, `media.senscritique.com`, `apollo.senscritique.com`

## Warnings

- Endpoint GraphQL non officiel — peut changer sans préavis.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `SENSCRITIQUE`.
