"""Fonctions pures d'analyse territoriale : GeoJSON et valeurs choroplèthes."""
import math


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def preparer_couche(zones, indicateurs, normaliser, champ="population"):
    """Associe les polygones aux indicateurs sans interpolation implicite."""
    if champ not in ("population", "densite_hab_km2"):
        raise ValueError("Indicateur cartographique non pris en charge.")
    lookup = {normaliser(r["quartier"]): r for r in indicateurs}
    collection = []
    valeurs = []
    for quartier in zones:
        donnees = lookup.get(normaliser(quartier["quartier"]), {})
        population = _num(donnees.get("population"))
        area = _num(donnees.get("superficie_km2"))
        densite = (population / area) if population is not None and area and area > 0 else None
        valeur = population if champ == "population" else densite
        if valeur is not None:
            valeurs.append(valeur)
        collection.append({
            "type": "Feature",
            "properties": {
                "NOM": quartier["quartier"],
                "Population": f"{population:,.0f}".replace(",", " ") if population is not None else "Non disponible",
                "Superficie": f"{area:.2f} km²" if area is not None else "Non disponible",
                "Densité": f"{densite:,.0f} hab./km²".replace(",", " ") if densite is not None else "Non disponible",
                "valeur": valeur,
            },
            "geometry": quartier["geometry"],
        })
    return {"type": "FeatureCollection", "features": collection}, valeurs


def score_disponibilite(table, champ="population"):
    """Nombre de quartiers dont l'indicateur numérique est réellement connu."""
    return sum(_num(row.get(champ)) is not None for row in table)
