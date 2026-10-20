"""Vérification des graphiques régionaux HTML : sécurité, zéro et ordre."""
import re
import pytest
from app.regional_charts import graphique_indicateur_regions, graphique_barres


def test_pourcentages_ordonnes_et_echelle_zero():
    html = graphique_indicateur_regions([
        {"nom_region": "Capitale-Nationale", "faible_revenu_familles_2023_pct": 5.3},
        {"nom_region": "Nord-du-Québec", "faible_revenu_familles_2023_pct": 21.3},
    ], "faible_revenu_familles_2023_pct")
    assert html.index("Nord-du-Québec") < html.index("Capitale-Nationale")
    assert "0 — échelle proportionnelle" in html
    assert 'width:100.0000%' in html
    assert re.search(r'width:24\.8826%', html)
    assert "21,3 %" in html and "5,3 %" in html
    assert "· 2023" in html


def test_noms_complets_et_annees_et_unites():
    html = graphique_indicateur_regions([
        {"nom_region": "Gaspésie–Îles-de-la-Madeleine", "population_2025": 92084}
    ], "population_2025")
    assert "Gaspésie–Îles-de-la-Madeleine" in html
    assert "92 084 hab." in html
    assert "· 2025" in html


def test_echappement_html_et_valeur_manquante():
    html = graphique_barres([
        {"nom": "<script>alert(1)</script>", "nombre": 1},
    ], "nom", "nombre", "Statistique <2026>")
    assert "&lt;script&gt;" in html
    assert "&lt;2026&gt;" in html
    assert "<script>" not in html
    with pytest.raises(ValueError, match="inconnu"):
        graphique_indicateur_regions([], "indicateur_faux")
    with pytest.raises(ValueError, match="indisponible"):
        graphique_indicateur_regions([{"nom_region": "A"}], "population_2025")
    with pytest.raises(ValueError, match="invalide"):
        graphique_indicateur_regions([
            {"nom_region": "A", "population_2025": -3}
        ], "population_2025")


def test_zero_ne_provoque_pas_de_division_par_zero():
    html = graphique_barres([
        {"nom": "A", "nombre": 0}
    ], "nom", "nombre", "Zéro")
    assert "width:0.0000%" in html
