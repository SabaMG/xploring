# Analyse préliminaire — SAÉ DataValueXploring

**Rôle incarné :** DOT / voirie de collectivité territoriale (gestionnaire d'infrastructure routière)
**Jeu de données :** US Accidents (Feb 2016 → Mar 2023), 7 728 394 lignes, 46 colonnes, 49 États
**Outils :** PySpark 4.1.1 (local), Parquet partitionné par État, binning H3 + carte Folium

---

## 1. Chiffres clés issus de l'EDA

### Volumétrie et couverture
- **7,73 M lignes** — PySpark + Parquet justifiés : pandas pur imposerait des allers-retours disque non viables sur ce volume
- **49 États** couverts, distribution très déséquilibrée :
  - Top 3 = **41 %** du dataset : CA (1,74 M), FL (880 k), TX (583 k)
  - Plusieurs États < 50 k accidents → puissance statistique locale faible

### Cible métier : la sévérité (échelle 1–4)
| Severity | Lignes | % |
|---|---:|---:|
| 1 (faible) | 67 366 | 0,87 % |
| 2 | 6 156 981 | 79,67 % |
| 3 | 1 299 337 | 16,81 % |
| 4 (grave) | 204 710 | **2,65 %** |

→ **Classe très déséquilibrée.** Pour la classification ML, trois options : regrouper (3+4 vs 1+2), pondérer les classes (`class_weight`), ou sur-échantillonner les classes minoritaires (SMOTE).

### Valeurs manquantes (impact pipeline)
| Colonne | % NA | Conséquence |
|---|---:|---|
| `end_lat`, `end_lng` | **44 %** | Emprise géographique inexploitable — on travaille uniquement sur `start_lat/lng` |
| `precipitation_in` | 28,5 % | Feature météo dégradée, à imputer prudemment |
| `wind_chill_f` | 25,9 % | Redondante avec `temperature_f` → supprimée |
| `wind_speed_mph` | 7,4 % | Gérable par imputation médiane |
| Autres météo | ~ 2 % | Acceptable |
| `sunrise_sunset` / twilights | 0,3 % | Acceptable |

### Infrastructure (delta de sévérité avec / sans la feature)
| Feature | Delta sévérité (avec − sans) |
|---|---:|
| **junction** | **+0,092** ⚠️ |
| give_way | −0,034 |
| railway | −0,054 |
| traffic_calming | −0,085 |
| no_exit | −0,101 |
| bump | −0,118 |
| stop | −0,140 |
| station | −0,141 |
| amenity | −0,144 |
| roundabout | −0,144 |
| traffic_signal | −0,144 |
| **crossing** | **−0,167** |

→ `junction` est la **seule feature qui augmente la sévérité moyenne**. Tous les aménagements équipés la diminuent. Ce résultat est directement actionnable : un carrefour `junction=true` sans équipement est un candidat prioritaire à l'étude.

> **Précaution méthodologique :** ces deltas sont observationnels, pas causaux. Un feu de circulation peut être associé à moins de sévérité parce qu'il régule la vitesse, *ou* parce qu'il a été installé sur des axes déjà moins accidentogènes. Aucun panel avant/après ne permet de trancher ici. Les résultats sont à présenter comme des *corrélations* et des *signaux de priorisation*, pas comme des preuves d'efficacité.

### Météo (résultat contre-intuitif)
- **Sévérité la plus haute** : Overcast 2,39 — Clear 2,37 — Scattered Clouds 2,38
- **Sévérité la plus basse** : Fair 2,13 — Fog 2,15
- Heavy Rain 2,26 — moins grave que par temps clair

→ Hypothèse : par beau temps, les vitesses pratiquées sont plus élevées → énergie cinétique plus forte → chocs plus graves. À creuser, mais **le message simpliste « la pluie tue » est contredit par ces données**. La météo ne suffit pas seule à expliquer la sévérité ; c'est la combinaison conditions + vitesse + infrastructure qui compte.

### Jour vs Nuit
- Jour : 5,33 M accidents (sévérité 2,209)
- Nuit : 2,37 M accidents (sévérité 2,219)

→ L'écart de sévérité est négligeable. En revanche, le **volume nocturne est sur-représenté** rapporté à la durée réelle de la nuit → le risque par heure est nettement plus élevé la nuit.

---

## 2. Deux types de problèmes, deux réponses distinctes

La clé de voûte de notre approche est la distinction entre deux natures de risque que le DOT doit traiter différemment :

### Problèmes structurels
Un lieu est dangereux **en permanence**, indépendamment des conditions du moment. La cause est dans l'infrastructure elle-même : géométrie du carrefour, absence d'équipement, tracé défavorable.

**Réponse métier :** travaux d'aménagement, équipement, étude de sécurité.
**Traduction data :** détection de zones à risque persistant par clustering géospatial (H3) et score de risque agrégé sur toute la période.

### Problèmes conjoncturels
Un lieu devient dangereux **sous certaines conditions** : heure de pointe, météo dégradée, période de vacances, obscurité. Hors de ces conditions, il ne se distingue pas.

**Réponse métier :** mesures temporaires — signalétique dynamique, limitation contextuelle de vitesse, alertes sur panneaux à messages variables.
**Traduction data :** modèle prédictif de sévérité dont les features d'entrée sont les conditions du moment (heure, météo, luminosité, saison).

Ces deux composantes sont **complémentaires** dans la solution finale : la carte des points noirs identifie *où* intervenir structurellement, le modèle prédictif indique *quand* déclencher des mesures temporaires.

---

## 3. Formulation du problème ML

### Composante 1 — Détection de points noirs (risque structurel)

**Tâche :** agrégation géospatiale + scoring, pas une classification supervisée classique.

**Pipeline :**
1. Binning H3 résolution 8–9 sur `start_lat/lng` (cellules ~0,5 km²)
2. Agrégation Spark : `count`, `avg(severity)`, distribution des features infra
3. Score de risque = `count × avg(severity)` normalisé
4. Ranking des cellules, export GeoJSON → carte Folium interactive

**Entraînement :** sur l'ensemble du dataset US — la généricité est l'atout du modèle. Démonstration appliquée à la Californie (volume suffisant : 1,74 M lignes).

**Livrable actionnable :** liste des 50 zones prioritaires avec, pour chacune, le nombre d'accidents, la sévérité moyenne, le type d'infrastructure dominant, les conditions météo et horaires les plus fréquentes.

### Composante 2 — Prédiction de sévérité (risque conjoncturel)

**Tâche :** classification supervisée (sévérité 1–4, ou binaire grave/non-grave).

**Features retenues :**
- Météo : `temperature_f`, `humidity_pct`, `visibility_mi`, `wind_speed_mph`, `weather_condition`
- Temporel : heure, jour de la semaine, mois, indicateur nuit/jour
- Infrastructure : toutes les features booléennes (`junction`, `traffic_signal`, `crossing`…)
- Géographique : État, zone urbaine/rurale (via densité H3)

**Features exclues :** `wind_chill_f` (redondante), `end_lat/lng` (44 % NA), `description` (NLP hors scope).

**Modèle :** `RandomForestClassifier` ou `GBTClassifier` via Spark MLlib. Choix justifié par la robustesse aux valeurs manquantes, l'interprétabilité des importances de features, et la scalabilité sur 7,73 M lignes.

**Gestion du déséquilibre :** regroupement binaire (sévérité ≥ 3 = grave) + `classWeight` dans MLlib.

**Entraînement :** sur l'ensemble du dataset US — le modèle doit être générique et applicable à n'importe quel territoire. Évaluation sur un split temporel (train avant 2022, test 2022–2023) pour simuler un usage réel.

**Livrable actionnable :** pour une zone et des conditions données (ex. "carrefour de type junction, 7h du matin, temps couvert, lundi"), le modèle prédit la probabilité d'un accident grave. Utilisable pour calibrer les alertes dynamiques.

---

## 4. Ce qui est faisable avec ces données

| Objectif | Faisable ? | Approche |
|---|---|---|
| Cartographier les **points noirs** | ✅ | Clustering H3 + score de risque agrégé |
| Identifier les **carrefours junction à équiper** | ✅ | Filtre `junction=true AND traffic_signal=false`, ranking H3 |
| **Prédire la sévérité** selon les conditions | ✅ | Random Forest / GBT, features météo + infra + temporel |
| Mesurer l'**effet apparent** des aménagements | ✅ | Delta sévérité avec/sans feature (observationnel) |
| **Saisonnalité** des risques | ✅ | `groupBy(state, month, hour)` + heatmap |
| **Risque nocturne** par heure | ✅ | Normalisation volume / durée de plage horaire |
| Modèle prédictif de **durée de blocage** | ⚠️ partiel | `end_time − start_time` douteux (44 % NA sur `end_lat/lng`) |

## 5. Ce qui n'est pas faisable (les « deuils »)

| Renoncement | Raison |
|---|---|
| **Causalité** d'un aménagement | Pas de panel avant/après. Les deltas sont des corrélations, pas des effets causaux. |
| **Profils conducteurs** | Aucune donnée individuelle (âge, alcool, vitesse au moment du choc) |
| **Coût réel** des accidents | `severity` est le seul proxy disponible — pas de données économiques |
| **Évaluation ex-post** d'une politique | Pas de marqueur temporel d'installation des équipements |
| **Couverture homogène par État** | Biais de reporting MapQuest/Bing : peu de lignes ≠ peu d'accidents |
| **Comparaison internationale** | Données US uniquement |
| **Emprise géographique** des accidents | 44 % de `end_lat/lng` manquants → `start_lat/lng` uniquement |
| **Description textuelle** | Non structurée, NLP hors scope |

---

## 6. Spécificité du rôle DOT vs analyses génériques

### Analyses génériques (peu différenciantes)
- « Il y a plus d'accidents en heure de pointe »
- « La pluie est dangereuse » — et c'est **contredit par nos données**
- « La sévérité est plus élevée la nuit » — l'écart est en réalité négligeable
- Classification globale Severity 1–4 sans contexte d'usage

> Ces analyses sont du *common knowledge* ou visibles dans n'importe quel rapport sécurité routière. Les livrer en l'état n'apporte aucune valeur à un acteur métier.

### Analyses spécifiques DOT (différenciantes, actionnables)

**a) Carte opérationnelle des points noirs**
Réponse à : *« Où investir mon prochain euro de travaux ? »*
Classement des zones H3 par score de risque structurel, avec profil de chaque zone (type d'infra dominant, conditions fréquentes). Priorité aux cellules `junction=true` sans équipement.

**b) Modèle de prédiction contextuelle**
Réponse à : *« Ce carrefour est-il à risque ce matin, dans ces conditions ? »*
Probabilité de sévérité grave selon les conditions en temps réel. Utilisable pour déclencher des alertes dynamiques ou des limitations temporaires de vitesse.

**c) Carrefours junction à étudier en priorité**
Filtre `junction=true AND traffic_signal=false AND severity≥3`, agrégé par zone H3.
Réponse à : *« Voici les 50 intersections où une étude d'équipement est justifiée. »*

**d) Plages horaires et conditions aggravantes par zone**
Identifier les couples (zone, contexte) où la sévérité est la plus élevée.
Réponse à : *« Quand et où activer les panneaux à messages variables ? »*

### Ce qui n'intéresse pas un DOT
| Analyse | Rôle concerné |
|---|---|
| Tarification par profil conducteur / zip code | Assureur |
| Durée d'impact sur le trafic | Opérateur GPS / navigation |
| Coût humain agrégé pour communication | Organisme de prévention |
| Évitement de zones à risque pour flotte | Logisticien |

---

## 7. Choix techniques justifiés

| Choix | Justification |
|---|---|
| **PySpark 4.1.1** | 7,73 M lignes → pandas impraticable en mémoire. Spark permet le traitement distribué local (`local[*]`) et la scalabilité vers un cluster si besoin. |
| **Parquet partitionné par État** | Lecture 10–50× plus rapide que le CSV pour les requêtes filtrées par État. Partitionnement cohérent avec les analyses géographiques. |
| **H3 (Uber)** résolution 8–9 | Grille hexagonale hiérarchique, meilleure pour les analyses de voisinage que les grilles carrées. Résolution 8 ≈ 0,7 km², résolution 9 ≈ 0,1 km² — adapté à l'échelle d'un carrefour. |
| **Spark MLlib** | Intégration native avec le DataFrame Spark — pas de conversion pandas intermédiaire. `RandomForestClassifier` et `GBTClassifier` disponibles, robustes au déséquilibre de classes. |
| **Folium** | Visualisation cartographique interactive en HTML, sans serveur. Lisible pour un décideur non-technique. |
| **Démonstration sur Californie** | Le modèle est entraîné sur tout le US (généricité). La Californie (1,74 M lignes, diversité urbain/rural) est utilisée pour la démonstration — volume suffisant pour des résultats significatifs et territoire connu. |

---

## 8. Proposition de valeur

Aujourd'hui, un DOT priorise ses interventions principalement sur la base de remontées terrain, d'accidents graves récents, ou de décisions politiques. La démarche est **réactive** et **peu systématique**.

Notre solution apporte deux capacités nouvelles :

1. **Priorisation proactive et data-driven** : un classement objectif des zones à risque structurel sur l'ensemble du territoire, indépendant des biais de perception ou des accidents récents médiatisés. Le DOT peut défendre ses choix d'investissement avec des données.

2. **Anticipation des conditions à risque** : un modèle capable de signaler, pour une zone et des conditions données, la probabilité d'un accident grave — base technique pour des alertes dynamiques ou des limitations temporaires de vitesse.

Ces deux livrables sont génériques (entraînés sur tout le US) et applicables à n'importe quel territoire disposant de données d'accidents structurées. La démonstration est faite sur la Californie.

---

## 9. Suite — pipeline technique

1. Notebook `02_points_noirs.ipynb` — clustering H3 + score de risque, carte Folium (Californie)
2. Notebook `03_modele_severite.ipynb` — pipeline MLlib, évaluation, feature importance
3. Consolidation du rapport L1 avec les résultats des deux notebooks