"""Calculs géospatiaux descriptifs à l'échelle des régions du Québec.

Sources : polygones MRNF déjà chargés et simplifiés pour le navigateur.
Les superficies sont des *estimations cartographiques* géodésiques, pas des
superficies administratives officiellement certifiées. Aucun indicateur
socioéconomique n'est extrapolé à partir des géométries.
"""
import math

from pyproj import Geod
from shapely.geometry import shape

WGS84 = Geod(ellps="WGS84")


def superficie_geodesique_km2(geometry):
    """Surface géodésique sur WGS84 en km² (îles et trous inclus)."""
    geom = shape(geometry)
    if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("La géométrie doit être un polygone non vide.")
    surface_m2, _ = WGS84.geometry_area_perimeter(geom)
    value = abs(surface_m2) / 1_000_000
    if not math.isfinite(value) or value <= 0:
        raise ValueError("La superficie géodésique calculée n'est pas valide.")
    return value


def tableau_regions(features):
    """Une ligne par code régional; erreur explicite en cas de doublon."""
    lignes = []
    codes = set()
    for feature in features:
        properties = feature.get("properties") or {}
        code = str(properties.get("code") or "").strip()
        nom = str(properties.get("nom") or "").strip()
        if not code.isdigit() or not nom or not feature.get("geometry"):
            raise ValueError("Code, nom ou géométrie de région manquant.")
        if code in codes:
            raise ValueError(f"Code régional dupliqué : {code}")
        codes.add(code)
        lignes.append({
            "Code régional": code.zfill(2),
            "Région administrative": nom,
            "Superficie géodésique estimée (km²)": round(
                superficie_geodesique_km2(feature["geometry"]), 1
            ),
        })
    if not lignes:
        raise ValueError("Aucune région cartographique disponible.")
    return sorted(lignes, key=lambda row: row["Code régional"])


def comparer_regions(lignes, code_a, code_b):
    """Comparer deux régions distinctes, sans ratios économiques déduits."""
    table = {row["Code régional"]: row for row in lignes}
    if code_a == code_b:
        raise ValueError("Sélectionnez deux régions différentes.")
    if code_a not in table or code_b not in table:
        raise ValueError("Code régional absent du tableau.")
    a, b = table[code_a], table[code_b]
    surface_key = "Superficie géodésique estimée (km²)"
    return {
        "Région A": a["Région administrative"],
        "Région B": b["Région administrative"],
        "Superficie A (km²)": a[surface_key],
        "Superficie B (km²)": b[surface_key],
        "Écart de superficie (km²)": round(
            a[surface_key] - b[surface_key], 1
        ),
    }
