"""Tests unitaires ANN (fixtures XML, hors réseau)."""
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

# Les scrapers community importent MetaKavita au runtime — tests lancés avec
# PYTHONPATH pointant vers l'install MetaKavita.
from ann import AnnScraper, _map_age, _parse_year, _upgrade_cover

SAMPLE = """<?xml version="1.0"?>
<ann>
  <manga id="4354" type="manga" name="Death Note" precision="manga">
    <info type="Picture" src="https://cdn.animenewsnetwork.com/thumbnails/fit200x200/encyc/A4354-41.jpg"/>
    <info type="Main title">Death Note</info>
    <info type="Alternative title" lang="JA">デスノート</info>
    <info type="Genres">drama</info>
    <info type="Genres">mystery</info>
    <info type="Themes">shinigami</info>
    <info type="Objectionable content">TA</info>
    <info type="Plot Summary">Shinigami notebooks.</info>
    <info type="Vintage">2003-12-01 to 2006-05-15 (serialized in Weekly Shonen Jump)</info>
    <info type="Vintage">2005-10-04 (North America)</info>
    <staff><task>Story</task><person id="1">Tsugumi Ohba</person></staff>
    <staff><task>Art</task><person id="2">Takeshi Obata</person></staff>
  </manga>
</ann>
"""


def test_upgrade_cover():
    src = "https://cdn.animenewsnetwork.com/thumbnails/fit200x200/encyc/A4354-41.jpg"
    assert "/max500x600/" in _upgrade_cover(src)


def test_parse_year_prefers_earliest():
    assert _parse_year("2003-12-01 to 2006 | 2005-10-04 (NA)") == 2003


def test_map_age():
    assert _map_age("TA") == "suggestive"
    assert _map_age("G") == "safe"
    assert _map_age("AO") == "pornographic"
    assert _map_age(None) is None


def test_extract_id():
    s = AnnScraper()
    assert (
        s.extract_id_from_url(
            "https://www.animenewsnetwork.com/encyclopedia/manga.php?id=4354"
        )
        == "4354"
    )
    assert s.extract_id_from_url("4354") == "4354"
    assert s.extract_id_from_url("https://example.com/x") is None


def test_build_candidate():
    s = AnnScraper()
    el = ET.fromstring(SAMPLE.encode("utf-8")).find("manga")
    cand = s._build_candidate(el)
    assert cand is not None
    assert cand["title"] == "Death Note"
    assert cand["year"] == 2003
    assert cand["age_rating"] == "suggestive"
    assert "/max500x600/" in cand["cover_url"]
    assert "Drama" in cand["genres"] or "drama" in [g.lower() for g in cand["genres"]]
    assert any(t.lower() == "shinigami" for t in cand["tags"])
    assert cand["staff"][0]["node"]["name"]["full"] == "Tsugumi Ohba"
    assert cand["format"] == "manga"
    assert "status" not in cand
    assert cand["url"].endswith("id=4354")


def test_fetch_by_id():
    s = AnnScraper()
    root = ET.fromstring(SAMPLE.encode("utf-8"))

    def fake_get_xml(session, params):
        return root

    with patch.object(s, "_get_xml", side_effect=fake_get_xml):
        with patch("ann.requests.Session", return_value=MagicMock()):
            meta = s.fetch("4354", library_type="Manga", is_id=True)

    assert meta is not None
    assert meta["title"] == "Death Note"
    assert meta["_match_score"] == 1.0
