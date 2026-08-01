"""Tests unitaires Planète BD (fixtures HTML, hors réseau)."""
from unittest.mock import MagicMock, patch

from planetebd import (
    PlanetebdScraper,
    _series_title_from_album_label,
    _normalize_isbn,
)

SAMPLE_SEARCH = """
<html><body>
<section class="search_result">
<article class="featured">
  <div class="image">
    <a href="/bd/albert-rene/asterix/asterix-en-lusitanie/58791.html#image"
       title="Astérix T41 : Astérix en Lusitanie (0), bd chez Albert René de Fabcaro, Conrad">
      <img src="https://static.planetebd.com/cover.jpg"/>
    </a>
  </div>
  <div class="text"><div class="cat">Bande dessinée</div></div>
</article>
<article class="featured">
  <div class="image">
    <a href="/comics/urban-comics/watchmen/-/49104.html#image"
       title="Watchmen, comics chez Urban Comics de Moore, Gibbons, Higgins">
      <img src="https://static.planetebd.com/watchmen.jpg"/>
    </a>
  </div>
  <div class="text"><div class="cat">Comics</div></div>
</article>
<article class="featured">
  <div class="image">
    <a href="/mangas/xxx/yyy/zzz/1.html" title="Some Manga">
      <img src="https://static.planetebd.com/m.jpg"/>
    </a>
  </div>
  <div class="text"><div class="cat">Mangas</div></div>
</article>
</section>
</body></html>
"""

SAMPLE_ALBUM = """
<html>
<head>
  <title>Astérix T41 : Astérix en Lusitanie (0), bd chez Albert René de Fabcaro, Conrad</title>
  <meta property="og:description" content="Résumé Astérix."/>
  <meta property="og:image" content="https://static.planetebd.com/cover.jpg"/>
  <meta property="og:isbn" content="9782017253709"/>
  <meta itemprop="datePublished" content="2025-10-23"/>
</head>
<body>
  <h1>Astérix T41</h1>
  <span itemprop="editor">Albert René</span>
  <a href="/recherche/genre/humour-2.html" itemprop="genre">Humour</a>
  <a href="/bd/series/asterix/1132.html">Astérix</a>
  <a href="/auteur/fabcaro/7339.html" title="Fabcaro">Fabcaro</a>
  <a href="/auteur/didier-conrad/820.html" title="Didier Conrad">Didier Conrad</a>
</body>
</html>
"""

SAMPLE_SERIES = """
<html><body>
  <h1>Astérix</h1>
  <p>Série en cours en français — 41 albums parus</p>
  <a href="/bd/albert-rene/asterix/asterix-en-lusitanie/58791.html">T41</a>
</body></html>
"""


def test_series_title_from_label():
    assert _series_title_from_album_label("Astérix T41 : Lusitanie") == "Astérix"
    assert _series_title_from_album_label("Watchmen T12") == "Watchmen"


def test_normalize_isbn():
    assert _normalize_isbn("978-2-01-725370-9") == "9782017253709"


def test_extract_id():
    s = PlanetebdScraper()
    assert (
        s.extract_id_from_url("https://www.planetebd.com/bd/series/asterix/1132.html")
        == "1132"
    )
    assert (
        s.extract_id_from_url(
            "https://www.planetebd.com/bd/albert-rene/asterix/x/58791.html"
        )
        == "58791"
    )


def test_search_filters_manga_keeps_bd_and_comics():
    s = PlanetebdScraper()
    session = MagicMock()
    session.get.return_value = MagicMock(status_code=200, text=SAMPLE_SEARCH)
    hits = s._search(session, "Astérix")
    assert len(hits) == 2
    assert hits[0]["series_key"].startswith("bd/")
    assert hits[1]["series_key"].startswith("comics/")


def test_parse_album_and_build():
    s = PlanetebdScraper()
    session = MagicMock()

    def fake_get(url, **kwargs):
        resp = MagicMock(status_code=200)
        if "/series/" in url:
            resp.text = SAMPLE_SERIES
        else:
            resp.text = SAMPLE_ALBUM
        return resp

    session.get.side_effect = fake_get
    cand = s._candidate_from_series_or_album(
        session,
        "https://www.planetebd.com/bd/albert-rene/asterix/asterix-en-lusitanie/58791.html",
        search_hint="Astérix",
    )
    assert cand is not None
    assert cand["title"] == "Astérix"
    assert cand["publisher"] == "Albert René"
    assert cand["year"] == 2025
    assert cand["isbn"] == "9782017253709"
    assert cand["staff"][0]["node"]["name"]["full"] == "Fabcaro"
    assert cand["cover_url"].endswith("cover.jpg")
    assert cand["status"] == "RELEASING"
    assert cand["format"] == "comic"
    assert "age_rating" not in cand
