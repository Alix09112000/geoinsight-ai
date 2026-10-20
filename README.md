# GeoInsight AI — Business Intelligence géospatiale du Québec

**Vision :** analyser, comparer et modéliser les territoires de toute la **province de Québec** (régions administratives, MRC, municipalités, quartiers), avec les données ouvertes et des méthodes géostatistiques.

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

## Feuille de route provinciale

1. Vue provinciale : polygones des 17 régions administratives depuis le service REST officiel du MRNF (affichage simplifié).\n2. Vue locale : quartiers de la ville de Québec.
3. Intégrer ensuite les limites des MRC et municipalités de la province.
4. Ajouter des indicateurs socioéconomiques harmonisés et leurs métadonnées.
4. Comparer les territoires à échelles comparables, avec estimation des incertitudes.
5. Développer la prédiction spatiale et la validation par blocs spatiaux.

Le périmètre du projet est la **province de Québec**; l’application ne prétend pas encore offrir une couverture provinciale complète.
