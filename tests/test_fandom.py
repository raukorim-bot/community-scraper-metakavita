"""Tests Fandom — résolution d'URL, parse wikitext/HTML, hors réseau."""
from __future__ import annotations

from unittest.mock import MagicMock

from fandom import (
    FandomRef,
    FandomScraper,
    clean_volume_title,
    first_isbn,
    is_cover_blurb,
    is_indexable_volume_page,
    pages_to_parse,
    parse_fandom_token,
    parse_fandom_url,
    parse_html_volumes,
    parse_volume_page_wikitext,
    parse_wikitext_volumes,
    pick_summary,
    score_ddg_ref,
    score_volume_list_title,
    series_alt_titles,
    series_name_to_slugs,
    series_name_to_wiki_url,
    to_en_wiki,
    split_edition_dates,
    to_iso_date,
    unwrap_ddg_href,
    upgrade_cover,
    volume_number_from_title,
    wiki_alias_slugs,
)

OP_HTML = """
<table>
<tr><th><a href="/wiki/Volume_1" title="Volume 1">Volume 1</a></th></tr>
<tr><th>X</th><th>Title</th><th>Release Date</th><th>Pages</th><th>ISBN</th></tr>
<tr><td>Japan</td><td>ROMANCE DAWN</td><td>December 24, 1997 [1]</td><td>208</td><td>978-4-08-872509-3</td></tr>
<tr><td>US</td><td>Romance Dawn</td><td>June 30, 2003 [1]</td><td>216</td><td>978-1-56931-901-7</td></tr>
<tr><td colspan="2"><dl><dt>Chapters</dt></dl><ul>
<li>1. <a href="/wiki/Chapter_1">Romance Dawn —The Dawn of the Adventure—</a></li>
<li>2. <a href="/wiki/Chapter_2">That Guy, "Straw Hat Luffy"</a></li>
</ul></td>
<td><img data-src="https://static.wikia.nocookie.net/onepiece/images/0/0e/Volume_1.png/revision/latest/scale-to-width-down/170?cb=1" src="data:image/gif;base64,R0lGODlhAQABAIABAAAAAP///yH5BAEAAAEALAAAAAABAAEAQAICTAEAOw%3D%3D"/></td></tr>
</table>
<table>
<tr><th>Volume 2</th></tr>
<tr><th>X</th><th>Title</th><th>Release Date</th><th>ISBN</th></tr>
<tr><td>Japan</td><td>VERSUS!!</td><td>April 3, 1998</td><td>9784088725441</td></tr>
<tr><td>US</td><td>Buggy the Clown</td><td>November 19, 2003</td><td>9781591160571</td></tr>
</table>
"""

NARUTO_HTML = """
<table>
<tr><th>#</th><th>Volume title</th><th>Japanese Release</th><th>English Release</th></tr>
<tr>
  <td><b>1</b></td>
  <td><i><a href="/wiki/Naruto_Uzumaki_(volume)" title="Naruto Uzumaki (volume)">Naruto Uzumaki</a></i></td>
  <td>3 March 2000</td>
  <td>6 August 2003</td>
</tr>
<tr><td colspan="4"><ul>
  <li>001. "<a href="/wiki/Naruto_Uzumaki!!_(chapter_1)">Naruto Uzumaki!!</a>"</li>
  <li>002. "<a href="/wiki/Konohamaru!!">Konohamaru!!</a>"</li>
</ul></td></tr>
</table>
"""

BERSERK_WIKITEXT = """
{{volinfo
| volume      = 1
| arcs        = [[Black Swordsman Arc]]
| ja pub      = 26 November 1990
| en pub      = 22 October 2003
| isbn        = * {{lang|ja|{{isbn|9784592135746}}}}
* {{lang|en|{{isbn|9781593070205}}}}
| episodes    = [[Black Swordsman Arc]] begins:
* 0-01. {{e|0-1}}
}}
{{Volume
|#=2
|JP Title=テスト
|US Title=The Black Swordsman
}}
"""


def test_series_name_to_slugs_compacts_spaces():
    assert series_name_to_slugs("One Piece")[0] == "onepiece"
    assert "attackontitan" in series_name_to_slugs("Attack on Titan")
    assert series_name_to_slugs("Berserk") == ["berserk"]
    slugs = series_name_to_slugs("A Couple of Cuckoos")
    assert slugs[0] == "acoupleofcuckoos"
    assert "cuckoo" in slugs
    assert "jojo" in series_name_to_slugs("JoJo's Bizarre Adventure")
    assert "komisan" in series_name_to_slugs("Komi Can't Communicate")
    assert "kaguyasama-wa-kokurasetai" in series_name_to_slugs("Kaguya-sama")
    assert "kusuriya-no-hitorigoto" in series_name_to_slugs("The Apothecary Diaries")
    assert wiki_alias_slugs("JoJo's Bizarre Adventure") == ["jojo"]


def test_series_name_to_wiki_url():
    assert series_name_to_wiki_url("One Piece") == "https://onepiece.fandom.com/"
    assert series_name_to_wiki_url("One Piece", lang="fr") == "https://onepiece.fandom.com/fr/"


def test_parse_fandom_url_and_token():
    ref = parse_fandom_url("https://onepiece.fandom.com/wiki/Chapters_and_Volumes/Volumes")
    assert ref == FandomRef(wiki="onepiece", page="Chapters and Volumes/Volumes")
    fr = parse_fandom_url("https://onepiece.fandom.com/fr/wiki/Liste_des_tomes")
    assert fr.wiki == "onepiece" and fr.lang == "fr" and fr.page == "Liste des tomes"
    assert parse_fandom_url("https://community.fandom.com/wiki/X") is None
    token = parse_fandom_token("onepiece/fr:Liste des tomes")
    assert token.wiki == "onepiece" and token.lang == "fr"


def test_extract_id_from_url():
    scraper = FandomScraper()
    assert (
        scraper.extract_id_from_url(
            "https://berserk.fandom.com/wiki/Releases_(Manga)"
        )
        == "berserk:Releases (Manga)"
    )
    assert scraper.extract_id_from_url("https://example.com/x") is None


def test_unwrap_ddg_and_cover_upgrade():
    href = (
        "//duckduckgo.com/l/?uddg=https%3A%2F%2Fonepiece.fandom.com%2Fwiki%2F"
        "Chapters_and_Volumes%2FVolumes&rut=abc"
    )
    assert unwrap_ddg_href(href).endswith("Chapters_and_Volumes/Volumes")
    cover = upgrade_cover(
        "https://static.wikia.nocookie.net/onepiece/images/0/0e/Volume_1.png/"
        "revision/latest/scale-to-width-down/170?cb=1"
    )
    assert cover.endswith("/revision/latest")
    assert upgrade_cover("data:image/gif;base64,xxx") == ""


def test_dates_and_isbn():
    assert to_iso_date("December 24, 1997 [1]") == "1997-12-24"
    assert to_iso_date("26 November 1990") == "1990-11-26"
    assert to_iso_date("May 15th, 2020") == "2020-05-15"
    assert to_iso_date("1998-04-03") == "1998-04-03"
    assert first_isbn("978-4-08-872509-3") == "9784088725093"
    assert split_edition_dates(
        "May 15th, 2020 (JP)<br>January 12th, 2021 (US)"
    ) == ("2021-01-12", "2020-05-15")


CUCKOO_VOLUME_WT = """
{{Volume Infobox
|title = Volume 1
|engname = A Couple of Cuckoos 1
|jpname = カッコウの許嫁 1
|release = May 15th, 2020 (JP)<br>January 12th, 2021 (US)
|isbn = 978-4-06-519380-8 (JP)<br>978-1-64-659893-9 (US)
}}
== Summary ==
Nagi Umino was switched at birth.
"""


def test_parse_volume_infobox_prefers_us_edition():
    payload = parse_volume_page_wikitext(CUCKOO_VOLUME_WT, fallback_number="1")
    assert payload["title"] == "A Couple of Cuckoos 1"
    assert payload["release_date"] == "2021-01-12"
    assert payload["isbn"] == "9781646598939"
    assert "switched at birth" in payload["summary"]


KOMI_INFOBOX_WT = """
{{Volume Infobox
|title = Volume 1
|jap_release = September 16, 2016
|jap_isbn = 978-4-09-127343-7
|eng_release = June 11, 2019
|eng_isbn = 978-19-7470-712-6
}}
"""


def test_parse_komi_infobox_prefers_english_release():
    payload = parse_volume_page_wikitext(KOMI_INFOBOX_WT, fallback_number="1")
    assert payload["release_date"] == "2019-06-11"
    assert payload["isbn"] == "9781974707126"


def test_parse_html_prefers_us_row():
    index = parse_html_volumes(OP_HTML, prefer_en=True)
    assert index["1"]["title"] == "Romance Dawn"
    assert index["1"]["release_date"] == "2003-06-30"
    assert index["1"]["isbn"] == "9781569319017"
    assert "Volume_1.png" in index["1"]["cover_url"]
    assert index["1"]["_page"] == "Volume 1"
    assert "Romance Dawn —The Dawn of the Adventure—" in index["1"]["_chapters"]
    assert index["2"]["title"] == "Buggy the Clown"


def test_parse_html_can_prefer_japan():
    index = parse_html_volumes(OP_HTML, prefer_en=False)
    assert index["1"]["title"] == "ROMANCE DAWN"
    assert index["1"]["release_date"] == "1997-12-24"
    assert index["1"]["isbn"] == "9784088725093"


def test_parse_wikitext_volinfo_and_volume():
    index = parse_wikitext_volumes(BERSERK_WIKITEXT)
    assert "title" not in index["1"]
    assert index["1"]["release_date"] == "2003-10-22"
    assert index["1"]["isbn"] == "9781593070205"
    assert "Black Swordsman Arc" in index["1"]["_extra"]
    assert index["2"]["title"] == "The Black Swordsman"


def test_parse_html_list_table_naruto():
    index = parse_html_volumes(NARUTO_HTML, prefer_en=True)
    assert index["1"]["title"] == "Naruto Uzumaki"
    assert index["1"]["release_date"] == "2003-08-06"
    assert index["1"]["_page"] == "Naruto Uzumaki (volume)"
    assert "Naruto Uzumaki!!" in index["1"]["_chapters"]


def test_parse_html_list_keeps_first_series_table():
    html = NARUTO_HTML + """
    <table>
    <tr><th>#</th><th>Volume title</th><th>Japanese Release</th><th>English Release</th></tr>
    <tr><td>1</td><td><a href="/wiki/Konoha_Shinden_Volume_1_(volume)">Mirai Sarutobi</a></td>
    <td>4 July 2024</td><td>9 July 2024</td></tr>
    </table>
    """
    index = parse_html_volumes(html, prefer_en=True)
    assert index["1"]["title"] == "Naruto Uzumaki"
    assert index["1"]["release_date"] == "2003-08-06"


def test_parse_html_skips_deluxe_isbn_table():
    html = """
    <table>
    <tr><th>No.</th><th>Publication date</th><th>ISBN</th><th>Contains</th></tr>
    <tr><td>1</td><td>27 February 2019</td><td>9781506711980</td><td>Volumes 1 – 3</td></tr>
    </table>
    """
    assert parse_html_volumes(html) == {}


GARDEN_VOLUME_WT = """
{{Template:Volume box
|title = Volume 1
|vol = 1
|isbn jp = 978-4088802657
|date jp = December 4, 2014
}}The first volume in the series.

==Chapters==
*[[Chapter 1|root 1. My Devil]]
*[[Chapter 2|root 2. Gardener & Devil]]

==Synopsis==
Awyn strives to be the perfect gardener to win over his human mistress.
"""


def test_volume_number_from_title_reads_volume_n():
    assert volume_number_from_title("Volume 1") == "1"
    assert volume_number_from_title("Vol. 2.5") == "2.5"
    assert volume_number_from_title("Volume 01") == "1"


def test_parse_volume_page_wikitext_box_and_synopsis():
    payload = parse_volume_page_wikitext(GARDEN_VOLUME_WT, fallback_number="1")
    assert payload["release_date"] == "2014-12-04"
    assert payload["isbn"] == "9784088802657"
    assert "perfect gardener" in payload["summary"]
    assert "My Devil" in payload["_chapters"]


def test_score_ddg_keeps_english_title_on_short_wiki_slug():
    ref = parse_fandom_url("https://cuckoo.fandom.com/wiki/A_Couple_of_Cuckoos_Wiki")
    assert score_ddg_ref("A Couple of Cuckoos", to_en_wiki(ref), []) > 0
    assert score_ddg_ref("A Couple of Cuckoos", FandomRef(wiki="manga", page="A Couple of Cuckoos"), []) < 0


def test_pick_summary_prefers_plot_then_chapters():
    assert is_cover_blurb("Volume 1 is titled X. The colored cover has a beige background.")
    assert not is_cover_blurb("Once upon a time, the Nine-Tailed Demon Fox devastated the village.")
    text = pick_summary(
        plot="Once upon a time, the fox attacked.",
        chapters="1. Naruto Uzumaki!!",
        cover="The colored cover has a beige background.",
    )
    assert text.startswith("Once upon a time")
    assert "Naruto Uzumaki!!" in text
    assert pick_summary(chapters="1. Romance Dawn", cover="The colored cover has a beige background.") == "1. Romance Dawn"


def test_score_volume_list_title():
    assert score_volume_list_title("List of Volumes") > score_volume_list_title("Volume 1")
    assert score_volume_list_title("Chapters and Volumes/Volumes") >= 8
    assert score_volume_list_title("Berserk (1997 Anime)") < 0
    assert score_volume_list_title("Tomes") < 6


def test_to_en_wiki_drops_localized_path():
    fr = parse_fandom_url("https://onepiece.fandom.com/fr/wiki/Liste_des_tomes")
    en = to_en_wiki(fr)
    assert en.wiki == "onepiece"
    assert en.lang == ""
    assert en.page == ""


def test_to_en_wiki_keeps_english_page_name():
    mixed = parse_fandom_url(
        "https://onepiece.fandom.com/fr/wiki/Chapters_and_Volumes/Volumes"
    )
    en = to_en_wiki(mixed)
    assert en.lang == ""
    assert en.page == "Chapters and Volumes/Volumes"


def test_pages_to_parse_tries_the_full_list_in_one_parse_order():
    pages = pages_to_parse(FandomRef(wiki="onepiece"))
    assert pages[0] == "Chapters and Volumes/Volumes"
    assert "Liste des tomes" not in pages


def test_hint_ref_reads_weblinks():
    scraper = FandomScraper()
    ref = scraper._hint_ref(
        None,
        {"webLinks": "https://anilist.co/manga/1, https://naruto.fandom.com/wiki/List_of_Volumes"},
    )
    assert ref is not None
    assert ref.wiki == "naruto"
    assert ref.lang == ""
    assert ref.page == "List of Volumes"


def test_series_alt_titles_keep_hunterpedia_matchable():
    alts = series_alt_titles("Hunter x Hunter", "Hunterpedia", "hunterxhunter")
    assert "hunter x hunter" in [a.lower() for a in alts]


def test_resolve_ref_skips_dead_compact_slug(monkeypatch):
    scraper = FandomScraper()
    session = MagicMock()

    def _siteinfo(_session, ref):
        if ref.wiki == "jujutsu-kaisen":
            return {"sitename": "Jujutsu Kaisen Wiki"}
        return None

    monkeypatch.setattr(scraper, "_siteinfo", _siteinfo)
    monkeypatch.setattr(scraper, "_ddg_refs", lambda *_a, **_k: [])
    ref = scraper._resolve_ref(session, "Jujutsu Kaisen", None, None)
    assert ref is not None
    assert ref.wiki == "jujutsu-kaisen"


def test_fetch_series_accepts_wiki_whose_sitename_is_not_the_title(monkeypatch):
    scraper = FandomScraper()
    session = MagicMock()
    monkeypatch.setattr(scraper, "_session", lambda: session)
    monkeypatch.setattr(
        scraper,
        "_resolve_ref",
        lambda *_a, **_k: FandomRef(wiki="hunterxhunter"),
    )
    monkeypatch.setattr(
        scraper, "_siteinfo", lambda *_a, **_k: {"sitename": "Hunterpedia"}
    )
    found = scraper.fetch("Hunter x Hunter", library_type="Manga")
    assert found is not None
    assert found["title"] == "Hunterpedia"
    assert found["_match_score"] >= 0.60
    session.close.assert_called()


def test_fetch_series_does_not_match_a_dead_slug(monkeypatch):
    scraper = FandomScraper()
    session = MagicMock()
    monkeypatch.setattr(scraper, "_session", lambda: session)
    monkeypatch.setattr(scraper, "_resolve_ref", lambda *_a, **_k: FandomRef(wiki="komicantcommunicate"))
    monkeypatch.setattr(scraper, "_siteinfo", lambda *_a, **_k: None)
    assert scraper.fetch("Komi Can't Communicate", library_type="Manga") is None
    session.close.assert_called()


def test_hint_ref_rewrites_french_wiki_to_en():
    scraper = FandomScraper()
    ref = scraper._hint_ref(
        "https://onepiece.fandom.com/fr/wiki/Liste_des_tomes",
        None,
    )
    assert ref == FandomRef(wiki="onepiece", page="", lang="")


def test_fetch_volume_index_uses_hint_and_parse(monkeypatch):
    scraper = FandomScraper()
    session = MagicMock()
    parsed = []

    def _parse(_session, _ref, page):
        parsed.append(page)
        return OP_HTML, ""

    monkeypatch.setattr(scraper, "_session", lambda: session)
    monkeypatch.setattr(scraper, "_parse_page", _parse)
    monkeypatch.setattr(
        scraper,
        "_pageprops_descriptions",
        lambda *_a, **_k: {
            "Volume 1": "Luffy sets sail and meets Zoro and Nami in a small port town."
        },
    )

    index = scraper.fetch_volume_index(
        "One Piece",
        library_type="Manga",
        series_id="https://onepiece.fandom.com/wiki/Chapters_and_Volumes/Volumes",
    )
    assert index is not None
    assert "1" in index
    assert index["1"]["title"] == "Romance Dawn"
    assert index["1"]["provider_ref"].endswith("#Volume_1")
    assert "Luffy sets sail" in index["1"]["summary"]
    assert "Romance Dawn —The Dawn of the Adventure—" in index["1"]["summary"]
    assert "<" not in index["1"]["summary"]
    assert parsed == ["Chapters and Volumes/Volumes"], (
        "la page liste entière se lit en un seul parse"
    )
    session.close.assert_called()


def test_fetch_volume_index_falls_back_to_volume_pages(monkeypatch):
    scraper = FandomScraper()
    session = MagicMock()

    monkeypatch.setattr(scraper, "_session", lambda: session)
    monkeypatch.setattr(scraper, "_parse_page", lambda *_a, **_k: ("", ""))
    monkeypatch.setattr(
        scraper,
        "_existing_titles",
        lambda *_a, **_k: [],
    )
    monkeypatch.setattr(scraper, "_volume_page_titles", lambda *_a, **_k: ["Volume 1", "Volume 2"])

    def _api(_session, _ref, params):
        titles = (params.get("titles") or "").split("|")
        pages = []
        for title in titles:
            number = title.rsplit(" ", 1)[-1]
            pages.append(
                {
                    "title": title,
                    "revisions": [
                        {
                            "slots": {
                                "main": {
                                    "content": (
                                        "{{Template:Volume box|vol="
                                        + number
                                        + "|isbn jp=978-4088802657|date jp=December 4, 2014}}\n"
                                        "==Synopsis==\nAwyn tends the garden.\n"
                                    )
                                }
                            }
                        }
                    ],
                    "thumbnail": {"source": "https://static.wikia.nocookie.net/garden/images/v.jpg"},
                }
            )
        return {"query": {"pages": pages}}

    monkeypatch.setattr(scraper, "_api", _api)
    monkeypatch.setattr(scraper, "_pageprops_descriptions", lambda *_a, **_k: {})
    monkeypatch.setattr(scraper, "_siteinfo", lambda *_a, **_k: {"sitename": "7thGARDEN Wiki"})

    index = scraper.fetch_volume_index("7th Garden", library_type="Manga")
    assert index is not None
    assert set(index) == {"1", "2"}
    assert index["1"]["isbn"] == "9784088802657"
    assert "garden" in index["1"]["summary"]


TANKOBON_WT = """
{{Tankobon
 | volume     = 1
 | release_ja = December 4, 2012
 | ISBN_ja    = 978-4-08-870701-3
 | release_en = February 16, 2016
 | ISBN_en    = 978-1-42-158564-2
 | title      = One Punch
}}
"""

VOLUMES_TMPL_WT = """
{{Volumes
|volume = 0
|title = Blinding Darkness
|release jp = December 4, 2018
|ISBN jp = ISBN 978-4088816722
|release eng = January 5, 2021
|ISBN eng = ISBN 978-1974720149
}}
"""

APOTHECARY_WT = """
{{Infobox:Volume
|vol_num        = Volume 1
|en_title       = The Apothecary Diaries, Volume 1
|date_jp        = September 25, 2017
|isbn13_jp      = 978-4-75-755489-4
|date_en        = December 8, 2020
|isbn13_en      = 978-1-64-609074-7
}}
== Synopsis ==
Maomao works in the inner palace.
"""

CHAINSAW_BOX_WT = """
{{Volume box
|title = Dog & Chainsaw
|vol = 1
|jp release = March 4, 2019<br><small>{{ISBN|978-4088817804}}</small>
|eng release = October 6, 2020<br><small>{{ISBN|978-1974709939}}</small>
}}
"""

TPN_HTML = """
<table>
<tr><th>Volume 1</th><th>Japanese Release Date:</th><th>English Release Date:</th></tr>
<tr><td></td><td>December 2, 2016</td><td>December 5, 2017</td></tr>
<tr><td>Grace Field House</td><td></td><td></td></tr>
</table>
"""


def test_parse_tankobon_and_volumes_templates():
    opm = parse_wikitext_volumes(TANKOBON_WT)
    assert opm["1"]["release_date"] == "2016-02-16"
    assert opm["1"]["isbn"] == "9781421585642"
    jjk = parse_wikitext_volumes(VOLUMES_TMPL_WT)
    assert jjk["0"]["title"] == "Blinding Darkness"
    assert jjk["0"]["release_date"] == "2021-01-05"
    assert jjk["0"]["isbn"] == "9781974720149"


def test_parse_infobox_volume_and_jp_release_fields():
    payload = parse_volume_page_wikitext(APOTHECARY_WT, fallback_number="1")
    assert payload["title"] == "The Apothecary Diaries, Volume 1"
    assert payload["release_date"] == "2020-12-08"
    assert payload["isbn"] == "9781646090747"
    assert "inner palace" in payload["summary"]
    csm = parse_wikitext_volumes(CHAINSAW_BOX_WT)
    assert csm["1"]["title"] == "Dog & Chainsaw"
    leaked = parse_wikitext_volumes("{{Volume box|vol=2|title=[[Dog & Chainsaw}}")
    assert leaked["2"]["title"] == "Dog & Chainsaw"
    assert csm["1"]["release_date"] == "2020-10-06"
    assert csm["1"]["isbn"] == "9781974709939"


def test_html_volume_block_does_not_use_date_as_title():
    index = parse_html_volumes(TPN_HTML, prefer_en=True)
    assert index["1"]["title"] == "Grace Field House"
    assert index["1"]["release_date"] == "2017-12-05"


def test_clean_title_and_volume_page_filter():
    assert clean_volume_title("December 4, 2020") == ""
    assert clean_volume_title("Pages: 192 (Japanese) Cover Character(s): Denji") == ""
    assert clean_volume_title("Chapters") == ""
    assert clean_volume_title("Romance Dawn") == "Romance Dawn"
    assert is_indexable_volume_page("Volume 1")
    assert is_indexable_volume_page("Manga Volume 01")
    assert not is_indexable_volume_page("Volume 1 (BD&DVD)")
    assert not is_indexable_volume_page("Episode Nagi Volume 1")
    assert not is_indexable_volume_page("Light Novel Volume 01")
