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
| **Version** | `1.0.1` |

## Summary

Anime-Planet — manga metadata (HTML).

## Quality / when to pick

EN manga — full payload + covers.

Gaps: `opt.: isbn, publisher, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Covers

`fetch_covers` prefers detail-page `og:image` (usually full JPEG) over search-card thumbs. Card URLs like `…-285x427.webp` are upgraded by stripping the WxH suffix. CDN hotlink needs MetaKavita image proxy (`requires_proxy` + `cdn.anime-planet.com`).

## Install (MetaKavita)

1. Download [`animeplanet.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/animeplanet.py) into `data/scrapers/`.
2. Verify SHA-256: `c3eb562a678283777e46fae8029d6fcd08a83cb8682662cb9aec97db6c227a68`.
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
