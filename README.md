# DataValueXploring - Réduire les accidents par la rénovation d'infrastructure

**Rôle incarné :** agence de voirie (DOT) d'une collectivité , **Données :** US Accidents
(Kaggle, 7,73 M accidents, 2016-2023) , **Fil rouge :** *où et quoi rénover, avec un budget limité ?*

## Ordre de lecture

| # | Dossier | Contenu | Livrable |
|---|---|---|---|
| 1 | `final/` | Rapport (PDF), présentation (pptx), poster A3 (PDF) | L1, L3, L4 |
| 2 | `rendu/` | **Notebook exécutable de bout en bout** + README + requirements figés + tests pytest + Dockerfile + source LaTeX du rapport + source du poster | **L2** |
| 3 | `interface/` | Explorateur Streamlit : diagnostic -> plan d'action -> validation, modèles paramétrables, tous les États | bonus |
| 4 | `pipeline/` | Pipeline CLI paramétrable par `config.yaml` (produit client) | bonus |
| 5 | `presentation/` | Sources des slides (markdown + générateur pptx + figures) | - |

## Démarrage rapide

```bash
pip install -r rendu/requirements.txt
jupyter notebook rendu/notebook.ipynb          # le livrable de référence (Run All)

pip install streamlit
python interface/prepare_data.py               # 1 fois (~1 min)
streamlit run interface/app.py                 # la démo interactive

python pipeline/run_pipeline.py --config pipeline/config.yaml   # le produit client
```

Chaque dossier a son README détaillé. Le notebook est la **source de vérité**
méthodologique ; interface et pipeline en répliquent le nettoyage et la méthode.
