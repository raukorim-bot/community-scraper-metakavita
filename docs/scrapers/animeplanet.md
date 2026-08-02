# Anime-Planet

| | |
|---|---|
| **ID** | `ANIMEPLANET` |
| **File** | [`animeplanet.py`](../../animeplanet.py) |
| **Types** | Manga |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.anime-planet.com |

## Summary

Anime-Planet — manga metadata (HTML).

## Quality / when to pick

EN manga — full payload + covers.

Gaps: `opt.: isbn, publisher, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`animeplanet.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/animeplanet.py) into `data/scrapers/`.
2. Verify SHA-256: `1257f6596fb4697d66ca589c9d302b94d00cb1f75ace5f539d8594fc8bccd615`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. rate_limit=3.0 s.

## Proxy domains (covers)

`anime-planet.com`, `www.anime-planet.com`, `cdn.anime-planet.com`

## Warnings

- Anti-bot fréquent — rate limit élevé.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ANIMEPLANET`.
