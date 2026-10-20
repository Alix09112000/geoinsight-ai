"""Indicateurs socioéconomiques régionaux, relevés des fiches officielles ISQ.

Une ligne par région administrative (code à deux chiffres). Millésimes:
population et proportion 65+ = 2025 (1er juillet), faible revenu des
familles = 2023, revenu disponible par habitant = 2024 (provisoire).
"""
import csv
from pathlib import Path

INDICATEURS = {
    "population_2025": ("Population (2025)", "hab.", 2025),
    "part_65_plus_2025_pct": ("Personnes de 65 ans et plus (2025)", "%", 2025),
    "faible_revenu_familles_2023_pct": ("Familles à faible revenu (2023)", "%", 2023),
    "revenu_disponible_2024_cad": ("Revenu disponible par habitant (2024, prov.)", "$", 2024),
}
COLONNES = ("code_region", "nom_region", *INDICATEURS, "source")


def charger_indicateurs_regions(path):
    """Validation stricte de la couverture et de la traçabilité officielle."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 17:
        raise ValueError("Le jeu ISQ doit contenir exactement 17 régions.")
    codes = {f"{index:02d}" for index in range(1, 18)}
    result = []
    seen = set()
    for row in rows:
        if not set(COLONNES).issubset(row):
            raise ValueError("Colonnes d'indicateurs manquantes.")
        code = str(row["code_region"]).strip().zfill(2)
        source = str(row["source"]).strip()
        if code not in codes or code in seen:
            raise ValueError("Code régional invalide ou dupliqué.")
        if source != f"https://statistique.quebec.ca/fr/vitrine/region/{code}":
            raise ValueError(f"URL de source officielle invalide : {code}")
        if not str(row["nom_region"]).strip():
            raise ValueError(f"Nom de région manquant : {code}")
        parsed = {"code_region": code, "nom_region": row["nom_region"].strip(),
                  "source": source}
        for field in INDICATEURS:
            try:
                val = float(row[field])
            except (ValueError, TypeError) as error:
                raise ValueError(f"{field}: valeur non numérique, région {code}") from error
            if not 0 <= val <= (100 if field.endswith("_pct") else 100_000_000):
                raise ValueError(f"{field}: valeur hors plage, région {code}")
            parsed[field] = int(val) if field in ("population_2025", "revenu_disponible_2024_cad") else val
        if parsed["population_2025"] <= 0:
            raise ValueError(f"Population nulle : {code}")
        result.append(parsed)
        seen.add(code)
    if seen != codes:
        raise ValueError("Une ou plusieurs régions administratives manquent.")
    return sorted(result, key=lambda r: r["code_region"])


def joindre_indicateurs_regions(features, rows):
    """Jointure stricte par code administratif, jamais par orthographe du nom."""
    lookup = {r["code_region"]: r for r in rows}
    if set(lookup) != {str(f["properties"]["code"]) for f in features}:
        raise ValueError("Les codes des indicateurs ne couvrent pas les mêmes régions que la carte.")
    return {code: lookup[code] for code in sorted(lookup)}


def format_indicateur(value, field):
    _, unit, _ = INDICATEURS[field]
    if unit == "%":
        return f"{value:.1f}".replace(".", ",") + " %"
    return f"{int(value):,}".replace(",", " ") + (" $" if unit == "$" else " hab.")
