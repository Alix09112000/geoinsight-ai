# GeoInsight AI — Intelligent Geospatial Business Intelligence

**Vision :** plateforme extensible de Business Intelligence géospatiale, de prédiction spatiale et d’aide à la décision pour les villes et territoires à l’échelle internationale.\n\n**Pilote disponible :** ville de Québec, Canada (version 2.0). Les premiers outils affichent ses quartiers, calculent des superficies géodésiques et permettent de comparer des indicateurs issus de données vérifiées. L’interface ne prétend pas encore gérer plusieurs villes.

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

## Déploiement web (Streamlit Community Cloud)

1. Ouvrir https://share.streamlit.io et se connecter avec GitHub.
2. Créer une nouvelle application depuis `Alix09112000/geoinsight-ai`, branche `main`.
3. Sélectionner le fichier d'entrée `app/main.py` puis déployer.
4. L'application télécharge les quartiers au premier démarrage; aucune base externe n'est obligatoire pour la version cartographique.

Lien public attribué après le déploiement, sur un sous-domaine `streamlit.app`.

## Feuille de route multi-territoires

- Référentiel des territoires (pays → régions → villes → subdivisions administratives), avec identifiants stables et métadonnées de sources.
- Connecteurs de données par pays/ville; harmonisation des coordonnées, unités, dates et définitions.
- Schémas spatiaux génériques dans PostGIS plutôt que des tables propres aux quartiers de Québec.
- Comparaisons territoriales uniquement sur des indicateurs méthodologiquement comparables.
- Modèles prédictifs, validation spatiale et indicateurs d’incertitude.
- Accès multilingue et visualisations 2D/3D.

L’extension multi-villes est **planifiée, non encore développée**.
