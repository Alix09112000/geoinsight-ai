# GeoInsight AI — Ville de Québec

Plateforme personnelle de **Business Intelligence géospatiale** (version 2.0). Elle affiche les quartiers de Québec, calcule les superficies géodésiques et permet de comparer des indicateurs territoriaux importés à partir de sources vérifiées.

## Installation (Windows)

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 -m etl.ingest_quartiers
py -3.11 -m streamlit run app/main.py
```

Ouvrir http://localhost:8501

## Fonctionnalités
- Carte Folium/OpenStreetMap avec filtre par quartier et zoom automatique.
- Superficies des quartiers mesurées géodésiquement sur WGS84.
- Tableau, graphiques et export CSV.
- Import de données socioéconomiques par quartier avec colonnes obligatoires `quartier,source,annee` et indicateurs optionnels `population,revenu_median`.
- Base de données PostgreSQL/PostGIS optionnelle (voir `docker-compose.yml`, `.env.example` et `sql/`).

Les fichiers `data/quartiers.geojson` et `data/indicateurs_quartiers.csv` ne sont **pas versionnés**. Générer le premier avec l'ETL et fournir uniquement des statistiques réellement établies pour le second. Attention aux limites de l'interpolation entre aires de diffusion et quartiers municipaux. **Aucun modèle prédictif n'est encore entraîné.**

Source : Ville de Québec / Données Québec. Projet expérimental, sans affiliation officielle avec la Ville.
