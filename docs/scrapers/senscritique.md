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
2. Verify SHA-256: `c5df9c5625307a20e44ead5d73b375c7c6a306c5f88450ef8ba959ce3341ec81`.
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
