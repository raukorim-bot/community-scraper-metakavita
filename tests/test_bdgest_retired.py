"""Garde-fou de retrait : BDGEST reste dans le catalogue, et reste retiré.

BDGEST a été retiré le 2026-08-13. Sa recherche propre était morte : il
interrogeait bedetheque.com de bout en bout, comme BEDETHEQUE que MetaKavita
livre déjà en core. Le motif décisif n'est pas le doublon mais la cadence,
indexée sur l'identifiant du scraper : deux entrées visant le même hôte tenaient
deux horloges qui ne se voyaient pas, et activer les deux frappait
bedetheque.com à la somme des deux cadences. C'est ce trafic qui a fait bannir
une IP.

Deux régressions sont possibles, et ce module couvre les deux :

* l'entrée **disparaît** du catalogue — l'utilisateur qui a déjà le fichier sous
  `data/scrapers/` se retrouve avec un orphelin dont l'interface ne sait plus
  dire pourquoi il ne faut pas s'en servir ;
* l'entrée **redevient installable** — un `status` remis à « beta » par une
  régénération partielle, un tag perdu au tri.

Un second scraper visant bedetheque.com serait la même erreur sous un autre nom
et il est refusé ici aussi.

Aucun accès réseau : on relit les fichiers du dépôt.
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RETIRED_ID = "BDGEST"
REPLACEMENT_ID = "BEDETHEQUE"
SHARED_HOST = "bedetheque.com"

# Copie de `services/scraper_store.py` (MetaKavita). Le catalogue ne peut pas
# importer l'application : il doit tourner sans elle. Ces deux ensembles sont
# donc dupliqués — c'est le contrat de fichier entre les deux dépôts, et le
# test échouerait si le catalogue publiait un mot que l'image ne reconnaît pas.
_RETIRED_STATUSES = frozenset({"retired", "deprecated", "archived", "dead", "unmaintained"})
_RETIRED_TAGS = frozenset({"retired", "deprecated", "archived", "dead", "unmaintained", "hors-usage"})


def is_entry_retired(entry: dict) -> bool:
    """`services.scraper_store.is_entry_retired`, à l'identique."""
    if not isinstance(entry, dict):
        return False
    if entry.get("retired") is True:
        return True
    if str(entry.get("lifecycle") or "").strip().lower() in _RETIRED_STATUSES:
        return True
    if str(entry.get("status") or "").strip().lower() in _RETIRED_STATUSES:
        return True
    return any(str(t).strip().lower() in _RETIRED_TAGS for t in entry.get("tags") or [])


def _load(*parts: str) -> dict:
    return json.loads((ROOT.joinpath(*parts)).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog_entry() -> dict:
    entries = [
        e
        for e in _load("store", "catalog.json").get("scrapers") or []
        if e.get("id") == RETIRED_ID
    ]
    assert entries, (
        f"{RETIRED_ID} a disparu de store/catalog.json. Une entrée retirée doit "
        "y rester : c'est le seul canal par lequel MetaKavita peut dire à qui a "
        "déjà le fichier pourquoi il ne faut plus s'en servir. Supprimée, elle "
        "ne laisse qu'un badge « retiré du magasin » sans motif."
    )
    return entries[0]


def test_meta_declares_the_retirement():
    """`store/meta.json` est la source ; le générateur ne fait que la recopier."""
    meta = _load("store", "meta.json").get(RETIRED_ID)
    assert meta, f"{RETIRED_ID} a disparu de store/meta.json."
    assert is_entry_retired(meta), f"{RETIRED_ID} n'y est plus marqué retiré."

    retirement = meta.get("retirement") or {}
    assert retirement.get("replacement") == REPLACEMENT_ID
    assert retirement.get("date")
    for lang in ("reason_fr", "reason_en"):
        assert (retirement.get(lang) or "").strip(), (
            f"{lang} manquant : sans motif publié, l'utilisateur n'a aucun moyen "
            "de savoir ce qu'il perd en supprimant le fichier."
        )


def test_the_published_catalog_refuses_the_install(catalog_entry):
    assert is_entry_retired(catalog_entry), (
        f"{RETIRED_ID} est redevenu installable. `install_from_catalog` ne rend "
        "un 403 que si l'entrée porte encore l'un des marqueurs de retrait."
    )


def test_all_four_signals_survive_a_partial_edit(catalog_entry):
    """Aucun des quatre marqueurs ne doit porter le retrait à lui seul.

    `is_entry_retired` en accepte quatre ; les publier tous fait qu'une reprise
    partielle du catalogue — un `status` réécrit, un tag perdu — laisse le
    refus d'installation en place.
    """
    assert catalog_entry.get("retired") is True
    assert catalog_entry.get("lifecycle") == "retired"
    assert catalog_entry.get("status") == "retired"
    assert "retired" in {str(t).lower() for t in catalog_entry.get("tags") or []}


def test_the_replacement_is_still_shipped():
    """Retirer sans remplaçant laisserait les bibliothèques BD FR sans source."""
    ids = {e.get("id") for e in _load("store", "catalog.json").get("scrapers") or []}
    assert REPLACEMENT_ID in ids


def test_only_one_live_scraper_targets_the_shared_host():
    """Un hôte, un scraper — la cadence est indexée sur l'id du scraper.

    Deux entrées actives sur bedetheque.com y frappent à la somme de leurs
    cadences, chacune ignorant l'autre. C'est exactement ce que le retrait de
    BDGEST corrige, et réintroduire un second scraper sur ce site le déferait.
    """
    live = [
        e.get("id")
        for e in _load("store", "catalog.json").get("scrapers") or []
        if not is_entry_retired(e)
        and any(SHARED_HOST in str(d).lower() for d in e.get("proxy_domains") or [])
    ]
    assert live == [REPLACEMENT_ID], (
        f"{SHARED_HOST} doit n'être visé que par {REPLACEMENT_ID}, or : {live}."
    )


def test_the_scraper_file_stays_in_the_repo(catalog_entry):
    """`verify_catalog_sha.py` relit le `.py` de chaque entrée du catalogue.

    Retirer l'entrée du catalogue mais garder le fichier serait sans effet ;
    garder l'entrée et supprimer le fichier casserait la vérification des
    empreintes. Le retrait vit dans les métadonnées, pas dans l'arborescence.
    """
    assert (ROOT / catalog_entry["file"]).is_file()


def test_the_live_smoke_run_skips_retired_scrapers():
    """Une campagne de mesure ne doit pas rouvrir la porte du bannissement."""
    from tests.run_live_smoke import _retired_files

    assert "bdgest.py" in _retired_files()
