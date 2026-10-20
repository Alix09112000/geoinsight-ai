"""Télécharger les limites municipales des quartiers de Québec depuis Données Québec."""
import argparse
import json
import os
from pathlib import Path
import requests

CKAN_API = "https://www.donneesquebec.ca/recherche/api/3/action/package_show"
DATASET = "vque_9"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "quartiers.geojson"

def choose_geojson_resource(resources):
    options = [r for r in resources if str(r.get("format", "")).lower() in ("geojson", "json") and str(r.get("url", "")).startswith("https://")]
    if not options:
        raise ValueError("Aucune ressource GeoJSON HTTPS disponible")
    return next((r for r in options if "geojson" in r.get("name", "").lower()), options[0])

def fetch_quartiers(session=requests):
    response = session.get(CKAN_API, params={"id": DATASET}, timeout=40)
    response.raise_for_status()
    data = response.json()
    if data.get("success") is not True:
        raise ValueError("Réponse du catalogue invalide")
    resource = choose_geojson_resource(data["result"]["resources"])
    response = session.get(resource["url"], timeout=90)
    response.raise_for_status()
    obj = response.json()
    if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
        raise ValueError("Réponse GeoJSON invalide")
    return obj, resource["url"]

def normalize_features(collection):
    seen, output = set(), []
    for f in collection["features"]:
        props = {str(k).upper(): v for k, v in (f.get("properties") or {}).items()}
        ident, name, geometry = props.get("ID"), props.get("NOM"), f.get("geometry")
        if ident is None or not str(name or "").strip() or not geometry:
            raise ValueError("Quartier sans ID, NOM ou géométrie")
        if str(ident) in seen:
            raise ValueError("Identifiant de quartier dupliqué")
        seen.add(str(ident))
        output.append((str(ident), str(name).strip(), geometry))
    if not output:
        raise ValueError("Aucun quartier trouvé")
    return output

def load_postgis(records, url, database_url):
    from sqlalchemy import create_engine, text
    engine = create_engine(database_url)
    ddl = Path(__file__).resolve().parents[1] / "sql" / "001_init.sql"
    with engine.begin() as conn:
        for statement in ddl.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                conn.execute(text(statement))
        for ident, name, geometry in records:
            conn.execute(text("""INSERT INTO quartiers (id, nom, geom, source_url)
                VALUES (:id, :nom, ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(:geom),4326)), :url)
                ON CONFLICT (id) DO UPDATE SET nom=EXCLUDED.nom, geom=EXCLUDED.geom,
                source_url=EXCLUDED.source_url, imported_at=NOW()"""),
                {"id": ident, "nom": name, "geom": json.dumps(geometry), "url": url})

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-db", action="store_true")
    args = parser.parse_args()
    obj, url = fetch_quartiers()
    records = normalize_features(obj)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    print(f"{len(records)} quartiers téléchargés; source : {url}")
    if args.load_db:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("Définir DATABASE_URL pour --load-db")
        load_postgis(records, url, db_url)

if __name__ == "__main__":
    main()
