"""Validation du graphique régional : échelle, labels et aucune valeur inventée."""
import pytest

from app.regional_charts import graphique_indicateur_regions


def test_pct_demarre_a_zero_et_trie_decroissant():
    chart = graphique_indicateur_regions([
        {"nom_region": "Nord-du-Québec", "faible_revenu_familles_2023_pct": 21.3},
        {"nom_region": "Capitale-Nationale", "faible_revenu_familles_2023_pct": 5.3},
    ], "faible_revenu_familles_2023_pct")
    spec = chart.to_dict()
    encoded = spec["layer"][0]["encoding"]
    assert encoded["x"]["scale"]["domain"][0] == 0
    assert encoded["x"]["scale"]["domain"][1] > 21.3
    assert encoded["y"]["sort"]["order"] == "descending"
    assert encoded["y"]["axis"]["labelLimit"] >= 300
    assert spec["height"] >= 380


def test_texte_valeur_annee_2023_et_unite():
    chart = graphique_indicateur_regions([
        {"nom_region": "Nord-du-Québec", "faible_revenu_familles_2023_pct": 21.3}
    ], "faible_revenu_familles_2023_pct")
    spec = chart.to_dict()
    assert spec["layer"][1]["encoding"]["text"]["field"] == "affichage"
    datasets = spec.get("datasets", {})
    assert any(
        r.get("affichage") == "21,3 %" and r.get("annee") == "2023"
        for rows in datasets.values() for r in rows
    )


def test_inconnus_et_manquants_refuses():
    with pytest.raises(ValueError, match="inconnu"):
        graphique_indicateur_regions([], "faux_indicateur")
    with pytest.raises(ValueError, match="indisponible"):
        graphique_indicateur_regions([{"nom_region": "A"}], "population_2025")
    with pytest.raises(ValueError, match="invalide"):
        graphique_indicateur_regions([
            {"nom_region": "A", "population_2025": -3}
        ], "population_2025")
