# -*- coding: utf-8 -*-
"""Tests du livrable : notebook valide et exécuté, invariants du CSV,
versions figées. Lancer depuis rendu/ : pytest tests/
"""
from pathlib import Path

import pandas as pd
import pytest

RENDU = Path(__file__).resolve().parent.parent

@pytest.fixture(scope="module")
def nb():
    nbformat = pytest.importorskip("nbformat")
    path = RENDU / "notebook.ipynb"
    assert path.exists(), "notebook.ipynb manquant"
    nb = nbformat.read(str(path), as_version=4)
    nbformat.validate(nb)
    return nb

def test_notebook_execute_sans_erreur(nb):
    """Aucune cellule ne doit porter une sortie d'erreur (Run All vert)."""
    erreurs = [
        o.get("ename")
        for c in nb.cells if c.cell_type == "code"
        for o in c.get("outputs", []) if o.get("output_type") == "error"
    ]
    assert erreurs == [], f"cellules en erreur : {erreurs}"

def test_notebook_est_execute(nb):
    """Le notebook livré doit embarquer ses résultats (outputs présents)."""
    avec_sortie = sum(1 for c in nb.cells if c.cell_type == "code" and c.get("outputs"))
    total = sum(1 for c in nb.cells if c.cell_type == "code")
    assert avec_sortie >= total * 0.8, f"seulement {avec_sortie}/{total} cellules avec sortie"

def test_notebook_contient_les_parties(nb):
    """Les sections A->E du cahier des charges sont présentes."""
    md = "\n".join("".join(c.source) for c in nb.cells if c.cell_type == "markdown")
    for section in ["## A", "## B", "## C", "## D", "## E"]:
        assert section in md, f"section manquante : {section}"

def test_notebook_sans_chemin_en_dur_specifique(nb):
    """Généricité : pas de dépendance à un fichier hors dépôt (hors dataset auto-téléchargé)."""
    code = "\n".join("".join(c.source) for c in nb.cells if c.cell_type == "code")
    assert "kagglehub" in code, "le téléchargement automatique des données doit être présent"
    for interdit in ["01_eda", "02_points", "03_modele", "04_expo", "accidents.parquet"]:
        assert interdit not in code, f"dépendance au brouillon détectée : {interdit}"

@pytest.fixture(scope="module")
def zones():
    path = RENDU / "zones_prioritaires.csv"
    assert path.exists(), "zones_prioritaires.csv manquant"
    return pd.read_csv(path)

def test_csv_schema(zones):
    attendues = {"rank", "h3_cell", "n_accidents", "charge", "avg_severity",
                 "dominant", "amenagement", "impact_graves_evites"}
    manquantes = attendues - set(zones.columns)
    assert not manquantes, f"colonnes manquantes : {manquantes}"

def test_csv_rangs_uniques_et_complets(zones):
    assert zones["rank"].is_unique
    assert zones["rank"].min() == 1
    assert len(zones) == zones["rank"].nunique()

def test_csv_invariants_metier(zones):
    assert zones["avg_severity"].between(1, 4).all()
    assert (zones["charge"] >= zones["n_accidents"]).all()
    ecart = (zones["charge"] - zones["n_accidents"] * zones["avg_severity"]).abs()
    assert (ecart <= zones["n_accidents"] * 0.01 + 5).all()
    assert (zones["impact_graves_evites"] >= 0).all()

def test_csv_cellules_h3_valides(zones):
    h3 = pytest.importorskip("h3")
    valid = getattr(h3, "is_valid_cell", None) or getattr(h3, "h3_is_valid")
    assert zones["h3_cell"].map(valid).all(), "cellule H3 invalide dans le CSV"

def test_csv_recommandations_variees(zones):
    """Garde-fou anti-artefact : la prescription ne doit pas être identique partout."""
    assert zones["amenagement"].nunique() >= 3

def test_requirements_versions_figees():
    txt = (RENDU / "requirements.txt").read_text()
    lignes = [l.strip() for l in txt.splitlines()
              if l.strip() and not l.strip().startswith("#")]
    non_figees = [l for l in lignes if "==" not in l]
    assert not non_figees, f"dépendances non figées : {non_figees}"

def test_artefacts_livres():
    assert (RENDU / "README.md").exists()
    carte = RENDU / "carte_zones_prioritaires.html"
    assert carte.exists() and carte.stat().st_size > 10_000, "carte absente ou vide"
