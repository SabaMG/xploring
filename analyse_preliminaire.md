# Analyse préliminaire — SAÉ DataValueXploring

**Rôle incarné :** DOT / voirie de collectivité territoriale (gestionnaire d'infrastructure routière)
**Jeu de données :** US Accidents (Feb 2016 → Mar 2023), 7 728 394 lignes, 46 colonnes, 49 États
**Outils :** PySpark 4.1.1 (local), Parquet partitionné par État, futur binning H3 + carte folium

---

## 1. Chiffres clés issus de l'EDA

### Volumétrie et couverture
- **7,73 M lignes** — Spark/Parquet justifié, pas faisable en pandas pur sans aller-retour disque
- **49 États** couverts, mais distribution très déséquilibrée :
  - Top 3 = **41 %** du dataset : CA (1,74 M), FL (880 k), TX (583 k)
  - Plusieurs États avec < 50 k accidents → puissance statistique faible localement

### Cible métier : la sévérité (échelle 1–4)
| Severity | Lignes | % |
|---|---:|---:|
| 1 (faible) | 67 366 | 0,87 % |
| 2 | 6 156 981 | 79,67 % |
| 3 | 1 299 337 | 16,81 % |
| 4 (grave) | 204 710 | **2,65 %** |

→ **Classe extrêmement déséquilibrée** : si on fait du ML de classification, il faudra rééquilibrer (oversampling SMOTE, class weights, ou regrouper 3+4 vs 1+2).

### Valeurs manquantes (impact pipeline)
| Colonne | % NA | Conséquence |
|---|---:|---|
| `end_lat`, `end_lng` | **44 %** | impossible de calculer une emprise géographique fiable de l'accident |
| `precipitation_in` | 28,5 % | feature météo dégradée |
| `wind_chill_f` | 25,9 % | redondante avec température → à supprimer |
| `wind_speed_mph` | 7,4 % | gérable par imputation |
| Autres météo | ~ 2 % | OK |
| `sunrise_sunset` / twilights | 0,3 % | OK |

### Infrastructure (`delta` sévérité avec/sans la feature)
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

→ **Seul `junction` augmente la sévérité moyenne**. Tous les autres aménagements la diminuent. Insight directement actionnable pour un DOT.

### Météo (contre-intuitif)
- **Sévérité la plus haute** : `Overcast` 2,39 — `Clear` 2,37 — `Scattered Clouds` 2,38
- **Sévérité la plus basse** : `Fair` 2,13 — `Fog` 2,15
- `Heavy Rain` 2,26 — moins grave que par temps clair

→ Hypothèse : par beau temps les vitesses sont plus élevées → chocs plus sévères. À creuser, mais **un message marketing simpliste « la pluie tue » est faux sur ces données**.

### Jour vs Nuit
- Jour : 5,33 M (sévérité 2,209)
- Nuit : 2,37 M (sévérité 2,219)

→ Écart de sévérité négligeable, mais le **volume nocturne est sur-représenté** vu la fraction du temps que représente la nuit → risque par heure plus élevé la nuit.

---

## 2. Ce qui est **faisable** avec ces données

| Objectif | Faisable ? | Approche |
|---|---|---|
| Cartographier les **points noirs** d'une zone | ✅ | Binning H3 (résolution 8–9) sur `start_lat/lng`, agrégation Spark, score = `count × avg(severity)` |
| Identifier les **carrefours à risque** | ✅ | Filtrage `junction = true` + agrégation géographique, comparaison avec/sans feu, croisement météo |
| Mesurer l'**effet apparent** d'un aménagement sur la sévérité | ✅ | Comparaison de sévérité moyenne avec/sans la feature, à conditions comparables (matching ou modèle) |
| Modèle prédictif de **sévérité** (1–4) | ✅ | Spark MLlib `RandomForestClassifier` ou `GBT`, features = météo + infra + heure + zone |
| Modèle prédictif de **durée de blocage** | ⚠️ partiel | `end_time − start_time` mais 44 % des `end_lat/lng` manquants laissent un doute sur la fiabilité des `end_time` |
| **Saisonnalité** des risques par zone | ✅ | `groupBy(state, month, hour)` + heatmap |

## 3. Ce qui n'est **pas faisable** (les « deuils »)

| Renoncement | Raison |
|---|---|
| **Causalité** d'un aménagement | Pas de panel temporel avant/après installation. Un carrefour avec feu corrélé à moins de sévérité ne prouve pas que le feu cause la baisse — le feu peut avoir été posé *parce que* le carrefour était à risque (effet rebond). Travail observationnel uniquement |
| **Profils conducteurs** | Aucune donnée individuelle (âge, expérience, alcool, vitesse au moment du choc) |
| **Coût** réel des accidents (€/$) | Absent — on peut seulement utiliser `severity` comme proxy |
| **Évaluation ex-post** d'une politique publique | Pas de marqueur « ce carrefour a été rénové en 2019 » |
| **Comparaison internationale** | Données US uniquement — un DOT français devrait recollecter |
| **Couverture homogène par État** | Source MapQuest / Bing → biais de reporting. Un État avec peu de lignes n'est pas forcément peu accidentogène, il peut être peu instrumenté |
| **Données manquantes `end_lat/lng`** (44 %) | L'emprise géographique de l'accident n'est pas exploitable — on se contentera de `start_lat/lng` comme point unique |
| **Description textuelle** | Non structurée, dépend de la source — exploitable seulement en NLP, hors scope |

## 4. Spécificité du rôle DOT vs analyses génériques

### Analyses **génériques** (utiles à tout le monde, peu différenciantes)
- « Il y a plus d'accidents en heure de pointe »
- « La pluie est dangereuse » (et en plus c'est **faux** sur ces données !)
- « La sévérité est plus élevée la nuit »
- Classification globale Severity 1–4 sans contexte d'usage

> Ces résultats sont du **commun knowledge** ou directement visibles dans n'importe quel rapport sécurité routière. Les livrer en l'état n'apporte aucune valeur à un acteur métier.

### Analyses **spécifiques DOT** (différenciantes, actionnables)

**a) Cartographie opérationnelle des points noirs** — livrable type :
- Liste classée des N cellules géographiques (H3) prioritaires d'un territoire choisi
- Pour chaque cellule : nombre d'accidents, sévérité moyenne, type de carrefour dominant, conditions météo dominantes
- **Question répondue :** « Où investir mon prochain euro de travaux ? »

**b) Effet apparent des aménagements** — exploiter le résultat le plus fort de l'EDA :
- **`crossing` : −0,167** sur la sévérité moyenne (passage piéton)
- **`traffic_signal` : −0,144** (feu de circulation)
- **`roundabout` : −0,144** (rond-point)
- **`junction` : +0,092** (intersection non aménagée)
- **Question répondue :** « Quels types d'aménagements semblent associés à une baisse de sévérité, à quelles conditions ? »
- Précaution méthodologique : matching ou stratification par densité de trafic et environnement urbain/rural pour limiter les biais de confusion. À documenter dans le rapport.

**c) Carrefours-junction à équiper en priorité**
- Filtrer `junction = true AND traffic_signal = false AND severity >= 3`
- Agréger par H3, classer par volume × sévérité
- **Question répondue :** « Voici 50 carrefours où une étude d'équipement est justifiée. »

**d) Plages horaires/météo aggravantes par zone**
- Identifier les couples (zone, contexte) où la sévérité explose
- Recommandation : signalétique dynamique, limitation contextuelle de vitesse
- **Question répondue :** « Quand et où mettre des alertes sur panneaux à messages variables ? »

### Ce qui **n'intéresserait pas un DOT** mais intéresse d'autres rôles

| Analyse | Rôle qui s'y intéresserait |
|---|---|
| Tarification par zip code / profil de conducteur | Assureur |
| Durée d'impact trafic (End−Start) | Opérateur GPS / navigation |
| Coût humain agrégé par campagne de comm | Sécurité routière / prévention |
| Optimisation de tournée éviter zones à risque | Logisticien / flotte |

→ **Le périmètre DOT est donc bien délimité : aménagement physique de l'infrastructure et priorisation budgétaire géographique.**

---

## 5. Périmètre choisi pour la suite

**Proposition :** se restreindre à un **État** ou une **métropole** pour itérer vite et produire un livrable lisible.

- **Candidat 1 — Californie** (CA, 1,74 M lignes) : volume maximal, mais probablement trop large pour une cartographie lisible
- **Candidat 2 — Los Angeles County** (sous-ensemble de CA) : équilibre volume/lisibilité, métropole emblématique
- **Candidat 3 — État médian** (ex. Caroline du Sud SC, 382 k) : volume gérable, hétérogénéité urbain/rural intéressante

À trancher avant de lancer la pipeline points noirs.

---

## 6. Suite immédiate

1. Trancher le périmètre géographique
2. Pipeline Spark v1 — **points noirs via H3** sur le périmètre choisi
3. Carte interactive folium / kepler
4. Documenter les choix techniques (rapport L1)
