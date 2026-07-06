# Interface interactive - DataValueXploring (livrable bonus)

Explorateur Streamlit qui complète le notebook : visualiser les résultats et
**(ré)entraîner les modèles de gravité avec différents paramètres**, sur
l'ensemble des États-Unis ou sur **n'importe quel État** (preuve de généricité
par la manipulation).

## Lancer

```bash
pip install streamlit                     # en plus de requirements.txt du rendu
python interface/prepare_data.py          # 1 fois (~3-5 min) : Spark -> parquet légers
streamlit run interface/app.py            # ouvre http://localhost:8501
```

## Ce qu'on peut faire

| Panneau | Interactions |
|---|---|
| **Barre latérale** | choix du **territoire** (US ou l'un des 49 États), de l'**algorithme** (LogReg / Arbre / RandomForest / HistGB), des **hyperparamètres** (profondeur, n_estimators, learning_rate…), du **périmètre d'entraînement** (US générique vs État seul), du **seuil de décision** et du class_weight |
| **📍 OÙ** | carte H3 des zones prioritaires du territoire (top-N réglable), courbe de concentration du risque, table des zones |
| **🔧 QUOI** | métriques du modèle entraîné avec vos paramètres (PR-AUC vs plancher, ROC-AUC), **matrice de confusion qui réagit au seuil**, courbe précision-rappel, **effets ajustés par g-computation** (quel équipement protège, à contexte égal) |
| **⏰ QUAND** | part d'accidents graves par heure / météo / mois **pour le territoire choisi** |

## Architecture (pourquoi c'est instantané)

```
prepare_data.py (Spark, 1 fois)                    app.py (Streamlit)
7,73 M lignes ──► accidents_sample.parquet ──────► (ré)entraînement paramétrable
              ──► zones.parquet (H3, 49 États) ──► cartes & concentration
              ──► quand_*.parquet             ──► analyses temporelles
```

L'app travaille sur un **échantillon stratifié** (≤ 40 000 lignes par État,
~1,46 M au total) : les entraînements prennent quelques secondes et sont mis en
cache. Les chiffres de **référence** restent ceux du notebook (`rendu/notebook.ipynb`),
calculés sur le dataset complet - l'interface est un outil d'exploration et de
démonstration, pas la source de vérité.

## Limites (assumées)

- Échantillon ≤ 40 k lignes/État -> les métriques peuvent différer légèrement du notebook.
- Les effets ajustés affichés sont **associationnels** (pas causaux), comme dans le rendu.
- Pas d'exposition OSM dans l'app (dépendance réseau) : le classement des zones est par charge.

## Option « historique du lieu » (mode ciblage - désactivée par défaut)

Par défaut, l'interface utilise **exactement les features du notebook et du
pipeline CLI** (cohérence entre les trois modes). Un interrupteur permet
d'ajouter l'**historique du lieu**
(taux d'accidents graves de la zone H3, à deux échelles), calculé **sur la
période d'entraînement uniquement** (anti-fuite, lissage bayésien) :
PR-AUC **0,147 -> 0,179** (×1,7 -> **×2,1** vs plancher), ROC-AUC 0,67 -> **0,71**.
L'onglet MODÈLE présente aussi le **pouvoir de ciblage** (courbe de gain) -
la lecture métier pertinente : *« en auditant les 10 % d'accidents les plus
risqués, on capture ~26 % des graves (×2,6 vs hasard) »*.
**Pourquoi opt-in :** l'historique du lieu contient déjà l'effet passé des
équipements - il améliore le ciblage mais peut **diluer l'attribution** ;
le moteur de preuve (notebook/CLI) l'exclut donc volontairement.
