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
| **Rate limit** | `4.0` s |
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
2. Verify SHA-256: `27f83546e4f08d9248c96a25fd70112b3d6b0d0c5b694a2d8518304a5c3aa42a`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. rate_limit=4.0 s (conservative).

## Proxy domains (covers)

`leagueofcomicgeeks.com`, `www.leagueofcomicgeeks.com`, `comicgeeks.app`, `s3.amazonaws.com`

## Warnings

- API officielle non disponible en libre-service.
- Rate limit élevé volontairement.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `LOCG`.
