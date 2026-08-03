# Wikidata

| | |
|---|---|
| **ID** | `WIKIDATA` |
| **File** | [`wikidata.py`](../../wikidata.py) |
| **Types** | Book, Comic, Manga |
| **Method** | Official API |
| **Status** | Beta |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | C / 70 |
| **Auth** | None |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | Global — en, fr, ja, de, es, it, ko, zh |
| **Site** | https://www.wikidata.org |

## Summary

Wikidata live (SPARQL + Entity API) — fallback / ISBN / cross-IDs. Limited metadata scope.

## Quality / when to pick

Fallback / ISBN / cross-IDs — limited scope, not a primary.

Gaps: `provider: status, tags; opt.: publisher, alternative_titles, isbn` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`wikidata.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/wikidata.py) into `data/scrapers/`.
2. Verify SHA-256: `a230580461140d10e6d2e73e2b2bf7d01071dc97abf3d7353e4c2b61fe5d961e`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic, Manga).

### Setup

No API key. rate_limit=1.2 s. Requires MetaKavita ≥ 1.6.1 (`scrapers.wikidata_map`).

## Proxy domains (covers)

`wikidata.org`, `www.wikidata.org`, `commons.wikimedia.org`, `upload.wikimedia.org`

## Warnings

- Périmètre de données limité — ne remplace pas AniList / ComicVine / Google Books.
- API live uniquement (pas de mode dump/SQLite hors-ligne).

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `WIKIDATA`.
