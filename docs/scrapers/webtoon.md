# WEBTOON

| | |
|---|---|
| **ID** | `WEBTOON` |
| **File** | [`webtoon.py`](../../webtoon.py) |
| **Types** | Manga |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 99 |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | KR/Global — en, fr |
| **Site** | https://www.webtoons.com |
| **Version** | `1.0.0` |

## Summary

WEBTOON (Line) — webtoons / manhwa (HTML). Does not invent publication status.

## Quality / when to pick

EN webtoon — covers + summary; year not exposed.

Gaps: `provider: year; opt.: isbn, publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`webtoon.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/webtoon.py) into `data/scrapers/`.
2. Verify SHA-256: `dde4a94c3f08b3bf547d05d48d4da85d12b550289c1d7e350a461620c2610f4f`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. rate_limit=2.5 s.

## Proxy domains (covers)

`webtoons.com`, `www.webtoons.com`, `swebtoon-phinf.pstatic.net`, `webtoon-phinf.pstatic.net`

## Warnings

- Gros site — rate limit recommandé.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `WEBTOON`.
