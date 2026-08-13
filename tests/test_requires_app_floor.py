"""Plancher de version : une copie ne doit pas être offerte à une image qui ne peut pas l'importer.

Contexte. Un scraper s'exécute dans MetaKavita, contre le `BaseScraper` et les
fonctions de `scrapers.utils` de la version installée. Les copies core publiées
ici appellent `self._http_get` et importent `response_is_ok`, qui n'existent
qu'à partir de la 1.7.0 : sur une image 1.6.x, l'import échoue et MetaKavita
délie le scraper. Le fournisseur disparaît alors de toutes les recherches, sans
rien à l'écran pour l'expliquer — le pire des symptômes, parce qu'il ressemble
à un site en panne.

Le catalogue est le seul endroit partagé par toutes les versions en service :
c'est donc lui qui porte le plancher, via `requires_app` dans `store/meta.json`.
Ces tests vérifient les deux moitiés du contrat : le plancher est déclaré là où
il est nécessaire, et il survit à la prochaine resynchronisation des copies
core — car c'est en la relançant qu'on l'effacerait sans s'en apercevoir.

Aucun import de scraper, aucun réseau : lecture syntaxique et JSON.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FLOOR = "1.7.0"

# Helpers apparus en 1.7.0. `_http_get` / `_http_post` portent la cadence par
# requête ; `response_is_ok` et `provider_error_scope` distinguent une clé
# révoquée d'un « aucun résultat ». Aucun des quatre n'existe en 1.6.x.
NEW_METHODS = {"_http_get", "_http_post"}
NEW_UTILS = {"response_is_ok", "provider_error_scope"}

CATALOG = json.loads((ROOT / "store" / "catalog.json").read_text(encoding="utf-8"))
META = json.loads((ROOT / "store" / "meta.json").read_text(encoding="utf-8"))
BY_FILE = {entry["file"]: entry for entry in CATALOG["scrapers"]}


def _needs_v17(path: pathlib.Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in NEW_METHODS:
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("scrapers"):
            if any(alias.name in NEW_UTILS for alias in node.names):
                return True
    return False


NEEDING = sorted(p.name for p in ROOT.glob("*.py") if p.name in BY_FILE and _needs_v17(p))


def test_the_scan_still_finds_the_copies_it_is_meant_to_guard():
    """Si la détection casse, le test paramétré passerait à vide."""
    assert len(NEEDING) >= 20


@pytest.mark.parametrize("filename", NEEDING)
def test_a_copy_using_the_new_helpers_declares_the_floor(filename):
    entry = BY_FILE[filename]
    assert entry.get("requires_app") == FLOOR, (
        f"{filename} appelle un helper introduit en {FLOOR} mais son entrée de "
        f"catalogue n'annonce pas de plancher : une installation 1.6.x la "
        f"téléchargerait, échouerait à l'import, et perdrait le fournisseur."
    )


@pytest.mark.parametrize("filename", NEEDING)
def test_the_catalog_floor_comes_from_meta(filename):
    """Le catalogue est généré : un plancher qui n'est pas dans `meta.json` serait effacé au prochain build."""
    entry = BY_FILE[filename]
    assert META[entry["id"]].get("requires_app") == entry.get("requires_app")


def test_every_core_entry_declares_the_floor():
    """Les copies core sont publiées en bloc : aucune ne doit rester sans plancher."""
    without = sorted(
        e["id"] for e in CATALOG["scrapers"] if e.get("is_core") and not e.get("requires_app")
    )
    assert not without, f"entrées core sans plancher : {without}"


def test_the_floor_survives_a_core_resync():
    """`sync_core_from_metakavita` réécrit les entrées core depuis sa propre table.

    Cette table ne connaît pas `requires_app` — il est décidé à la main. Sans
    report explicite, relancer la synchronisation republierait les copies sans
    plancher, et l'erreur ne se verrait que chez les utilisateurs restés sur
    l'image précédente.
    """
    spec = importlib.util.spec_from_file_location(
        "sync_core", ROOT / "scripts" / "sync_core_from_metakavita.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    merged = module.merge_entry({"requires_app": FLOOR}, {"status": "stable"})
    assert merged.get("requires_app") == FLOOR
