"""Régressions sur les indicateurs ISQ de 17 régions administratives."""
from pathlib import Path

import pytest

from app.socioeconomic import (
    INDICATEURS, charger_indicateurs_regions, joindre_indicateurs_regions,
    format_indicateur,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "indicateurs_regions_isq.csv"


def test_snapshot_source_17_regions_complet_et_source_officielle():
    rows = charger_indicateurs_regions(DATA)
    assert len(rows) == 17
    assert {r["code_region"] for r in rows} == {
        f"{n:02d}" for n in range(1, 18)
    }
    assert all(
        row["source"] == f"https://statistique.quebec.ca/fr/vitrine/region/{row['code_region']}"
        for row in rows
    )
    qc = next(row for row in rows if row["code_region"] == "03")
    assert qc["population_2025"] == 814004
    assert qc["faible_revenu_familles_2023_pct"] == 5.3
    assert qc["revenu_disponible_2024_cad"] == 39597


def test_jointure_exige_les_17_codes():
    rows = charger_indicateurs_regions(DATA)
    features = [{"properties": {"code": code}} for code in
                (f"{n:02d}" for n in range(1, 18))]
    grouped = joindre_indicateurs_regions(features, rows)
    assert len(grouped) == 17
    assert grouped["06"]["nom_region"] == "Montréal"
    with pytest.raises(ValueError):
        joindre_indicateurs_regions(features[:-1], rows)


def test_millesimes_propres_a_chaque_indicateur():
    assert INDICATEURS["population_2025"][2] == 2025
    assert INDICATEURS["part_65_plus_2025_pct"][2] == 2025
    assert INDICATEURS["faible_revenu_familles_2023_pct"][2] == 2023
    assert INDICATEURS["revenu_disponible_2024_cad"][2] == 2024


def test_formatage():
    assert format_indicateur(814004, "population_2025") == "814 004 hab."
    assert format_indicateur(5.3, "faible_revenu_familles_2023_pct") == "5,3 %"
    assert format_indicateur(39597, "revenu_disponible_2024_cad") == "39 597 $"


def test_donnees_manquantes_ou_incoherentes_refusees(tmp_path):
    original = DATA.read_text(encoding="utf-8")
    truncated = tmp_path / "incomplet.csv"
    truncated.write_text("\n".join(original.splitlines()[:-1]), encoding="utf-8")
    with pytest.raises(ValueError, match="17 régions"):
        charger_indicateurs_regions(truncated)
    bad = tmp_path / "pourcentage_invalide.csv"
    bad.write_text(original.replace('"29.8"', '"129.8"', 1),
                   encoding="utf-8")
    with pytest.raises(ValueError, match="hors plage"):
        charger_indicateurs_regions(bad)
