# League of Comic Geeks

| | |
|---|---|
| **ID** | `LOCG` |
| **File** | [`locg.py`](../../locg.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `5.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://leagueofcomicgeeks.com |

## Summary

League of Comic Geeks — comic series via public XHR/HTML (partner API is not self-serve).

## Quality / when to pick

US comics, no API key — series covers + summary.

Gaps: `opt.: isbn, publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`locg.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/locg.py) into `data/scrapers/`.
2. Verify SHA-256: `be41223bdd57df6df6d5c31566df3a1a15ea32b1b3e9fcb7f2ef5f6d690736c4`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. rate_limit=5.0 s (interactive; do not bulk-crawl).

## Proxy domains (covers)

`leagueofcomicgeeks.com`, `www.leagueofcomicgeeks.com`, `comicgeeks.app`, `s3.amazonaws.com`

## Warnings

- robots.txt Crawl-delay: 30 targets search-engine bots. MetaKavita uses 5.0 s for interactive lookups only — prefer ComicVine/Metron for bulk sync.

- API officielle non disponible en libre-service.
- Interactive use only — prefer ComicVine/Metron for bulk.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `LOCG`.
