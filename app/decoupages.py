"""Accès aux découpages administratifs officiels du Québec (MRNF / ArcGIS REST)."""
import requests
import streamlit as st
from shapely.geometry import shape, mapping

BASE = "https://servicescarto.mern.gouv.qc.ca/pes/rest/services/Territoire/SDA_WMS/MapServer"
LAYERS = {
    "mrc": (1, "MRS_CO_MRC", "MRS_NM_MRC", "MRS_CO_REG"),
    "municipalite": (2, "MUS_CO_GEO", "MUS_NM_MUN", "MUS_CO_MRC"),
}

@st.cache_data(ttl=86400, show_spinner=False)
def charger_subdivisions(niveau: str, parent_code: str):
    """Récupère uniquement les entités du parent sélectionné, non tout le Québec."""
    if niveau not in LAYERS:
        raise ValueError("Niveau non supporté.")
    if not parent_code.isdigit() or len(parent_code) not in (2, 3):
        raise ValueError("Code de territoire invalide.")
    layer, code_field, name_field, parent_field = LAYERS[niveau]
    if (niveau == "mrc" and len(parent_code) != 2) or (niveau == "municipalite" and len(parent_code) != 3):
        raise ValueError("Longueur du code parent incorrecte.")

    response = requests.get(f"{BASE}/{layer}/query", params={
        "where": f"{parent_field}='{parent_code}'",
        "outFields": f"{code_field},{name_field},{parent_field}",
        "outSR": 4326,
        "returnGeometry": "true",
        "f": "geojson",
        "geometryPrecision": 5,
        "maxAllowableOffset": 0.002,
    }, timeout=90)
    response.raise_for_status()
    payload = response.json()
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Le service n'a pas retourné de GeoJSON valide.")
    output = []
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        code = str(props.get(code_field) or "").strip()
        name = str(props.get(name_field) or "").strip()
        geo = feature.get("geometry")
        if not code or not name or not geo:
            continue
        polygon = shape(geo)
        if polygon.is_empty or polygon.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        output.append({"type": "Feature",
                       "properties": {"code": code, "nom": name},
                       "geometry": mapping(polygon.simplify(0.001, preserve_topology=True))})
    return sorted(output, key=lambda feature: feature["properties"]["nom"])
