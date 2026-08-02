# Community scrapers — MetaKavita

Official community repository for **plug-and-play** metadata scrapers for [MetaKavita](https://github.com/raukorim-bot/MetaKavita).

Drop a `.py` file into your MetaKavita `data/scrapers/` folder, restart, and the provider appears in the UI.

> **Security:** installing a scraper runs arbitrary Python with the same privileges as MetaKavita. Only install files from this repository (or sources you trust). Full authoring rules: [`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md).

---

## Install

1. Copy the scraper `.py` file(s) you want into MetaKavita’s **`data/scrapers/`** directory  
   (Docker: the folder mapped to `/app/data/scrapers`, or your host `./data/scrapers`).
2. Restart MetaKavita.
3. Check **Config / providers** — the new source should be listed for the matching library type.

No rebuild of the MetaKavita image is required.

---

## Available scrapers

| File | ID | Types | Auth | Covers | Notes |
|------|-----|-------|------|--------|-------|
| [`babelio.py`](babelio.py) | `BABELIO` | Book | None | Yes | French literature (HTML) |
| [`senscritique.py`](senscritique.py) | `SENSCRITIQUE` | Book, Comic | None | Yes | FR — GraphQL Apollo |
| [`dnb.py`](dnb.py) | `DNB` | Book | None | No | Deutsche Nationalbibliothek (SRU MARC21) |
| [`metron.py`](metron.py) | `METRON` | Comic | **Required** | Yes | [metron.cloud](https://metron.cloud) API token → `METRON_API_KEY` |
| [`bangumi.py`](bangumi.py) | `BANGUMI` | Manga, Book | None* | Yes | Bangumi (`api.bgm.tv`) — JP/CN |
| [`ann.py`](ann.py) | `ANN` | Manga | None | Yes | Anime News Network encyclopedia (XML) |
| [`planetebd.py`](planetebd.py) | `PLANETEBD` | Comic | None | Yes | Planète BD — BD FR + comics US (HTML) |
| [`bnf.py`](bnf.py) | `BNF` | Book | None | No | BnF Catalogue (SRU Dublin Core) |
| [`decitre.py`](decitre.py) | `DECITRE` | Book | None | Yes | Decitre — HTML search + JSON-LD |
| [`animeplanet.py`](animeplanet.py) | `ANIMEPLANET` | Manga | None | Yes | Anime-Planet (HTML) |
| [`webtoon.py`](webtoon.py) | `WEBTOON` | Manga | None | Yes | WEBTOON / Line (HTML) |
| [`tapas.py`](tapas.py) | `TAPAS` | Manga | None | Yes | Tapas series (HTML) |
| [`mangasanctuary.py`](mangasanctuary.py) | `MANGASANCTUARY` | Manga | None | Yes | Manga-Sanctuary FR (HTML) |
| [`novelupdates.py`](novelupdates.py) | `NOVELUPDATES` | Book, Manga | Optional CF cookies | Yes | Cloudflare — paste `cf_clearance=…` in `NOVELUPDATES_API_KEY` |
| [`locg.py`](locg.py) | `LOCG` | Comic | **Required** | Yes | LoCG API — `client_id:client_secret` in `LOCG_API_KEY` |
| [`isbndb.py`](isbndb.py) | `ISBNDB` | Book | **Required (paid)** | Yes | [ISBNdb](https://isbndb.com/apidocs/v2) REST key → `ISBNDB_API_KEY` — **not live-tested** (paid plan) |
| [`bdgest.py`](bdgest.py) | `BDGEST` | Comic | None | Yes | BDgest / Bédéthèque best-effort HTML (finetune later) |
| [`gcd.py`](gcd.py) | `GCD` | Comic | Optional Basic | Yes* | Grand Comics Database — JSON `/api/` (HTML is CF-blocked) |

\*Bangumi expects a proper User-Agent (handled by the scraper).  
\*GCD cover URLs are on `files1.comics.org` (may need proxy / browser-like fetch).

### Skipped / blocked for now

| Provider | Reason |
|----------|--------|
| LibraryThing | Cloudflare JS challenge |
| Goodreads | Terms / anti-bot — not pursued |
| Nautiljon | IP bans / aggressive anti-bot (historical) |

### API keys

**Metron** — account on [metron.cloud](https://metron.cloud) → API Tokens → `METRON_API_KEY` (Bearer, or `user:password`).

**LoCG** — MetaKavita attend **deux valeurs collées** dans `LOCG_API_KEY` :

```text
client_id:client_secret
```

Ce n’est **pas** un login/mot de passe de compte LoCG. Ce sont les credentials d’application API (même modèle que le client [Himon](https://himon.readthedocs.io/)) :
- `client_id` → header `X-API-CLIENT`
- `client_secret` → header `X-API-KEY`
- le scraper appelle ensuite `/api/authorize` pour obtenir un bearer token

À obtenir via le programme développeur / API League of Comic Geeks (si tu n’as pas ces credentials, le provider restera inutilisable — pas de mode anonyme fiable).

**ISBNdb** — REST key payante depuis le dashboard isbndb.com → `ISBNDB_API_KEY`.  
**Non testé en live** dans ce dépôt : un abonnement payant est requis pour obtenir une clé.

**Novel Updates** — optional: browser `cf_clearance` cookie string in `NOVELUPDATES_API_KEY` (without it, CF usually blocks).

**GCD** — optional comics.org account as `user:password` in `GCD_API_KEY` (Basic auth, higher API quota). HTML is CF-blocked; scraper uses `/api/` only.

---

## Authoring / vibecoding

See **[`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md)** for the full contract (BaseScraper, scoring, tags/genres caps, `proxy_domains`, inheritance patterns).

---

## Contributing

1. Fork this repo
2. Add one `.py` file per provider (uppercase `id`, clear `display_name`, `supported_types`, `rate_limit`, `proxy_domains`)
3. Open a PR with a short description + how you tested (title search + covers if any)

### Smoke tests

From this repo, with MetaKavita on `PYTHONPATH`:

```bat
set PYTHONPATH=Z:\kavitafetcher
set METAKAVITA_ROOT=Z:\kavitafetcher
python -m pytest tests/test_ann.py tests/test_planetebd.py -q
python tests/run_live_smoke.py
```

Maintainer review required before merge.

---

## Licence

Same spirit as MetaKavita — use at your own risk. Metadata belongs to the respective upstream sites/APIs; respect their terms and rate limits.
