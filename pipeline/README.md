# Pipeline paramétrable - DataValueXploring (produit client)

Version **ligne de commande** de l'analyse : le client renseigne **ses données
et ses choix** dans `config.yaml`, lance une commande, et récupère figures,
CSV décisionnels, carte et résumé - sans toucher au code.

```bash
pip install -r rendu/requirements.txt pyyaml
python pipeline/run_pipeline.py --config pipeline/config.yaml
```

## Ce que le client contrôle (config.yaml)

| Section | Paramètres |
|---|---|
| `donnees` | chemin du CSV (ou téléchargement auto), **territoire** analysé, périmètre d'entraînement (US générique / local) |
| `analyses` | activer/désactiver **quand** , **ou** , **quoi** , **synthese** indépendamment |
| `parametres` | seuil « grave », résolution H3, nb de zones prioritaires, lift, effectifs minimaux |
| `modele` | algorithme (dummy / logistic / tree / random_forest / hist_gradient_boosting), hyperparamètres, plafond de lignes, class_weight, split temporel, effets (odds ratios / g-computation) |

## Sorties (dans `sorties.dossier`)

| Fichier | Contenu |
|---|---|
| `quand.png` | volume + % de graves par heure, % de graves par météo |
| `ou_concentration.png` , `ou_carte.html` , `ou_zones_prioritaires.csv` | concentration du risque, carte H3, top-N zones |
| `quoi_metriques.png` | matrice de confusion + courbe précision-rappel (vs plancher) |
| `quoi_odds_ratios.png/.csv` , `quoi_effets_ajustes.png` | effets nets de chaque équipement, confondants contrôlés |
| `synthese_recommandations.csv` | par zone : aléa local, aménagement recommandé, **impact estimé (graves évités)** |
| `resume.json` | récapitulatif machine-lisible de l'exécution |

## Les trois modes de consommation du projet

| Mode | Fichier | Pour qui |
|---|---|---|
| **Notebook** (référence) | `rendu/notebook.ipynb` | l'évaluateur / le data scientist - toute la démarche expliquée |
| **Interface** (exploration) | `interface/app.py` (Streamlit) | la démo / l'analyste - visualiser et tester les modèles interactivement |
| **Pipeline CLI** (production) | `pipeline/run_pipeline.py` | le client / l'exploitation - relancer l'analyse sur ses données, planifiable (cron) |

Les trois partagent le **même nettoyage et la même méthodologie** (répliqués du
notebook, qui reste la source de vérité documentée).

## Exemples

```bash
# Analyse complète du Texas, modèle local, 30 zones
#   -> donnees.territoire: TX, perimetre_entrainement: territoire,
#      parametres.zones_prioritaires: 30

# Seulement la carte des zones (pas de ML) :
#   -> analyses: {quand: false, ou: true, quoi: false, synthese: false}

# Comparer un modèle simple :
#   -> modele.algorithme: logistic  (hyperparametres: {C: 1.0})
```
