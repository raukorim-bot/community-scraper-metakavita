## Summary

- Site / API:
- Library types: Book / Manga / Comic
- Auth: none / Config key name:
- Covers: yes / no

## How to test

- Positive query → expected title:
- Negative query → `None`:
- Covers checked: yes / no
- Local commands run:

## Checklist

- [ ] One `.py` at repo root with unique uppercase `id`
- [ ] Follows [`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md) (no Selenium; unified scoring)
- [ ] Polite `rate_limit` + complete `proxy_domains`
- [ ] No secrets / API keys committed
- [ ] `store/meta.json` updated **or** explicitly left to maintainers
- [ ] Ran `python scripts/build_store_catalog.py` if meta/docs changed

## Notes for reviewers

<!-- CF, paid API, known gaps, rate-limit sensitivity, etc. -->
