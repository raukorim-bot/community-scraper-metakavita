# Community scrapers — MetaKavita

Official community repository for **plug-and-play** metadata scrapers for [MetaKavita](https://github.com/raukorim-bot/MetaKavita).

Drop a `.py` file into your MetaKavita `data/scrapers/` folder, restart, and the provider appears in the UI.

> **Security:** installing a scraper runs arbitrary Python with the same privileges as MetaKavita. Only install files from this repository (or sources you trust). Full authoring rules: [`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md).

**Docs:** per-scraper pages in [`docs/`](docs/README.md).  
**Quality / covers / which scraper to pick:** [`docs/QUALITY.md`](docs/QUALITY.md).  
**Store (MetaKavita):** machine catalog [`store/catalog.json`](store/catalog.json) — see [`store/README.md`](store/README.md).  
**Propose a scraper (PR):** [`CONTRIBUTING.md`](CONTRIBUTING.md).

---

## Install

1. Copy the scraper `.py` file(s) you want into MetaKavita’s **`data/scrapers/`** directory  
   (Docker: the folder mapped to `/app/data/scrapers`, or your host `./data/scrapers`).
2. Restart MetaKavita.
3. Check **Config / providers** — the new source should be listed for the matching library type.

No rebuild of the MetaKavita image is required.

> **Check the version first.** An entry may require a minimum MetaKavita version — its doc page then opens with *Requires MetaKavita x.y.z or newer*. The Store honours that floor for you; a file copied by hand does not, and an image below it unbinds the scraper at import, so the provider simply never appears. The 21 core copies currently require **1.7.0**, and `WIKIDATA` requires **1.6.1**.

---

## Available scrapers

| File | ID | Types | Auth | Covers | Notes | Doc |
|------|-----|-------|------|--------|-------|-----|
| [`babelio.py`](babelio.py) | `BABELIO` | Book | None | Yes | French literature (HTML) | [doc](docs/scrapers/babelio.md) |
| [`senscritique.py`](senscritique.py) | `SENSCRITIQUE` | Book, Comic | None | Yes | FR — GraphQL Apollo | [doc](docs/scrapers/senscritique.md) |
| [`dnb.py`](dnb.py) | `DNB` | Book | None | No | Deutsche Nationalbibliothek (SRU MARC21) | [doc](docs/scrapers/dnb.md) |
| [`metron.py`](metron.py) | `METRON` | Comic | **Required** | Yes | [metron.cloud](https://metron.cloud) API token → `METRON_API_KEY` | [doc](docs/scrapers/metron.md) |
| [`bangumi.py`](bangumi.py) | `BANGUMI` | Manga, Book | None* | Yes | Bangumi (`api.bgm.tv`) — JP/CN | [doc](docs/scrapers/bangumi.md) |
| [`ann.py`](ann.py) | `ANN` | Manga | None | Yes | Anime News Network encyclopedia (XML) | [doc](docs/scrapers/ann.md) |
| [`planetebd.py`](planetebd.py) | `PLANETEBD` | Comic | None | Yes | Planète BD — French BD + US comics (HTML) | [doc](docs/scrapers/planetebd.md) |
| [`bnf.py`](bnf.py) | `BNF` | Book | None | No | BnF Catalogue (SRU Dublin Core) | [doc](docs/scrapers/bnf.md) |
| [`decitre.py`](decitre.py) | `DECITRE` | Book | None | Yes | Decitre — HTML search + JSON-LD | [doc](docs/scrapers/decitre.md) |
| [`animeplanet.py`](animeplanet.py) | `ANIMEPLANET` | Manga | None | Yes | Anime-Planet (HTML) | [doc](docs/scrapers/animeplanet.md) |
| [`webtoon.py`](webtoon.py) | `WEBTOON` | Manga | None | Yes | WEBTOON / Line (HTML) | [doc](docs/scrapers/webtoon.md) |
| [`tapas.py`](tapas.py) | `TAPAS` | Manga | None | Yes | Tapas series (HTML) | [doc](docs/scrapers/tapas.md) |
| [`mangasanctuary.py`](mangasanctuary.py) | `MANGASANCTUARY` | Manga | None | Yes | Manga-Sanctuary FR (HTML) | [doc](docs/scrapers/mangasanctuary.md) |
| [`novelupdates.py`](novelupdates.py) | `NOVELUPDATES` | Book, Manga | Optional CF cookies | Yes | Cloudflare — paste `cf_clearance=…` in `NOVELUPDATES_API_KEY` | [doc](docs/scrapers/novelupdates.md) |
| [`locg.py`](locg.py) | `LOCG` | Comic | None | Yes | LoCG site XHR/HTML — partner API not self-serve | [doc](docs/scrapers/locg.md) |
| [`isbndb.py`](isbndb.py) | `ISBNDB` | Book | **Required (paid)** | Yes | [ISBNdb](https://isbndb.com/apidocs/v2) — **not live-tested** | [doc](docs/scrapers/isbndb.md) |
| [`gcd.py`](gcd.py) | `GCD` | Comic | Optional Basic | Yes* | Grand Comics Database — JSON `/api/` | [doc](docs/scrapers/gcd.md) |
| [`openbd.py`](openbd.py) | `OPENBD` | Book | None | Yes | openBD JP — ISBN API + covers | [doc](docs/scrapers/openbd.md) |
| [`ndl.py`](ndl.py) | `NDL` | Book | None | No | NDL Search (National Diet Library JP) | [doc](docs/scrapers/ndl.md) |
| [`bne.py`](bne.py) | `BNE` | Book | None | No | Biblioteca Nacional de España (SRU) | [doc](docs/scrapers/bne.md) |
| [`loc.py`](loc.py) | `LOC` | Book | None | No | Library of Congress (SRU DC) | [doc](docs/scrapers/loc.md) |
| [`sbn.py`](sbn.py) | `SBN` | Book | None | No | SBN / ICCU Italia (OPAC JSON) | [doc](docs/scrapers/sbn.md) |
| [`kb.py`](kb.py) | `KB` | Book | None | No | KB Nederland (JSRU / GGC) | [doc](docs/scrapers/kb.md) |
| [`tebeosfera.py`](tebeosfera.py) | `TEBEOSFERA` | Comic | None | Yes | Tebeosfera — Spanish comics (HTML; limited) | [doc](docs/scrapers/tebeosfera.md) |
| [`wikidata.py`](wikidata.py) | `WIKIDATA` | Manga, Comic, Book | None | Yes | Wikidata live SPARQL/Entity — fallback / ISBN / cross-IDs (limited scope) | [doc](docs/scrapers/wikidata.md) |

\*Bangumi expects a proper User-Agent (handled by the scraper).  
\*GCD cover URLs are on `files1.comics.org` (may need proxy / browser-like fetch).

### Retired

Retired entries stay in [`store/catalog.json`](store/catalog.json) with `retired: true`: MetaKavita refuses to install them and flags the file for anyone who already has it. Deleting the entry instead would leave those users with a silent orphan.

| File | ID | Retired | Use instead | Why |
|------|-----|---------|-------------|-----|
| [`bdgest.py`](bdgest.py) | `BDGEST` | 2026-08-13 | `BEDETHEQUE` (core) | Its own search is dead — it queried bedetheque.com throughout, i.e. the same site as `BEDETHEQUE`, which does it better (CSRF token, ban 403 vs 404, ISO-8859-1, album index). Decisive point: throttling is keyed on the scraper id, so the two entries kept **two clocks for one host** and enabling both hit bedetheque.com at the sum of their rates. [doc](docs/scrapers/bdgest.md) |

### Skipped / blocked for now

| Provider | Reason |
|----------|--------|
| LibraryThing | Cloudflare JS challenge |
| Goodreads | Terms / anti-bot — not pursued |
| Nautiljon | IP bans / aggressive anti-bot (historical) |

### API keys

**Metron** — account on [metron.cloud](https://metron.cloud) → API Tokens → `METRON_API_KEY` (Bearer, or `user:password`).

**LoCG** — **no API key**. The official partner API (`client_id` / `client_secret`, [Himon](https://himon.readthedocs.io/) model) is **not** self-serve on the site; this scraper uses public series search / HTML+XHR pages. `/search` may sit behind Cloudflare; the endpoint we use (`/comic/get_comics`) was not CF-blocked in our tests.

**ISBNdb** — paid REST key from the isbndb.com dashboard → `ISBNDB_API_KEY`.  
**Not live-tested** in this repo: a paid subscription is required to obtain a key.

**Novel Updates** — optional: browser `cf_clearance` cookie string in `NOVELUPDATES_API_KEY` (without it, CF usually blocks).

**GCD** — optional comics.org account as `user:password` in `GCD_API_KEY` (Basic auth, higher API quota). HTML is CF-blocked; scraper uses `/api/` only.

---

## Authoring / vibecoding

Full BaseScraper contract (scoring, allowed libraries, `proxy_domains`, vibecoding prompt): **[`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md)**.

---

## Contributing (propose your scraper via PR)

Community scrapers are added through **GitHub Pull Requests**. Maintainers review security and matching quality before merge; merged scrapers are listed in [`store/catalog.json`](store/catalog.json).

**Step-by-step guide:** **[`CONTRIBUTING.md`](CONTRIBUTING.md)**

Short version:

1. Fork this repo and create a branch.
2. Add **one** `.py` at the repo root (uppercase `id`, `supported_types`, `rate_limit`, `proxy_domains`) following [`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md).
3. Test locally (positive + negative match; covers if any) with MetaKavita on `PYTHONPATH`.
4. Register the scraper in [`store/meta.json`](store/meta.json), then run `python scripts\build_store_catalog.py`.
5. Open a PR against `main` (use the PR template checklist).

Ideas without code yet → open a GitHub **Issue**.

### Smoke tests

```bat
set PYTHONPATH=Z:\kavitafetcher
set METAKAVITA_ROOT=Z:\kavitafetcher
python -m pytest tests/test_ann.py tests/test_planetebd.py -q
python tests/run_live_smoke.py
```

Maintainer review is required before merge.

---

## Licence

Same spirit as MetaKavita — use at your own risk. Metadata belongs to the respective upstream sites/APIs; respect their terms and rate limits.
