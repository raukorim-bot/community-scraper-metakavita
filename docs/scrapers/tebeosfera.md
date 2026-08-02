# Tebeosfera

| | |
|---|---|
| **ID** | `TEBEOSFERA` |
| **File** | [`tebeosfera.py`](../../tebeosfera.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Limited |
| **Covers (declared)** | Yes |
| **Covers (audit)** | No |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | ES — es |
| **Site** | https://www.tebeosfera.com |

## Summary

Tebeosfera — Spanish comics / tebeos (best-effort HTML).

## Quality / when to pick

ES comics — JS/iframe catalog, not scrapable yet.

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`tebeosfera.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/tebeosfera.py) into `data/scrapers/`.
2. Verify SHA-256: `da2c7d274727a6a28c425b1179ab743dff8b1b860fb42749b886d59049c42007`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. rate_limit=3.0 s.

## Proxy domains (covers)

`tebeosfera.com`, `www.tebeosfera.com`

## Warnings

- Catalogue entièrement JS/iframe — scraping HTML inopérant pour l’instant.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `TEBEOSFERA`.
