# -*- coding: utf-8 -*-
"""Prépare les données de l'interface (à lancer une fois).

Produit dans interface/data/ :
  - accidents_sample.parquet : échantillon stratifié par État (features + cible)
    -> permet de (ré)entraîner les modèles dans l'app, US entier ou par État
  - zones.parquet            : agrégats H3 rés. 8 pour TOUS les États (OÙ)
  - quand_hour.parquet / quand_weather.parquet / quand_event.parquet (QUAND)
"""
import os, sys, time
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data"); os.makedirs(OUT, exist_ok=True)
CANDIDATS = ["US_Accidents_March23.csv", "../US_Accidents_March23.csv",
             os.path.expanduser("~/Prog/Epita/ING2/xPloring/US_Accidents_March23.csv")]
CSV = next((p for p in CANDIDATS if os.path.exists(p)), None)
if CSV is None:
    import kagglehub
    d = kagglehub.dataset_download("sobhanmoosavi/us-accidents")
    CSV = next(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".csv"))

PER_STATE_CAP = 40_000   # lignes max par État dans l'échantillon d'entraînement
SEED = 42

from pyspark.sql import SparkSession, functions as F, Window
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                               DoubleType, BooleanType, TimestampType)

spark = (SparkSession.builder.master("local[*]").appName("interface_prep")
         .config("spark.driver.memory", "6g")
         .config("spark.sql.session.timeZone", "UTC").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

schema = StructType([StructField("ID",StringType()),StructField("Source",StringType()),
    StructField("Severity",IntegerType()),StructField("Start_Time",TimestampType()),
    StructField("End_Time",TimestampType()),StructField("Start_Lat",DoubleType()),
    StructField("Start_Lng",DoubleType()),StructField("End_Lat",DoubleType()),
    StructField("End_Lng",DoubleType()),StructField("Distance(mi)",DoubleType()),
    StructField("Description",StringType()),StructField("Street",StringType()),
    StructField("City",StringType()),StructField("County",StringType()),
    StructField("State",StringType()),StructField("Zipcode",StringType()),
    StructField("Country",StringType()),StructField("Timezone",StringType()),
    StructField("Airport_Code",StringType()),StructField("Weather_Timestamp",TimestampType()),
    StructField("Temperature(F)",DoubleType()),StructField("Wind_Chill(F)",DoubleType()),
    StructField("Humidity(%)",DoubleType()),StructField("Pressure(in)",DoubleType()),
    StructField("Visibility(mi)",DoubleType()),StructField("Wind_Direction",StringType()),
    StructField("Wind_Speed(mph)",DoubleType()),StructField("Precipitation(in)",DoubleType()),
    StructField("Weather_Condition",StringType()),StructField("Amenity",BooleanType()),
    StructField("Bump",BooleanType()),StructField("Crossing",BooleanType()),
    StructField("Give_Way",BooleanType()),StructField("Junction",BooleanType()),
    StructField("No_Exit",BooleanType()),StructField("Railway",BooleanType()),
    StructField("Roundabout",BooleanType()),StructField("Station",BooleanType()),
    StructField("Stop",BooleanType()),StructField("Traffic_Calming",BooleanType()),
    StructField("Traffic_Signal",BooleanType()),StructField("Turning_Loop",BooleanType()),
    StructField("Sunrise_Sunset",StringType()),StructField("Civil_Twilight",StringType()),
    StructField("Nautical_Twilight",StringType()),StructField("Astronomical_Twilight",StringType())])

INFRA = ["junction","crossing","stop","traffic_signal","railway","station",
         "roundabout","bump","give_way","no_exit","traffic_calming","amenity"]
WEATHER_NUM = ["temperature_f","humidity_pct","visibility_mi","wind_speed_mph","pressure_in"]

t0 = time.time()
raw = spark.read.option("header", True).schema(schema).csv(CSV)
raw = raw.toDF(*[c.lower().replace("(","_").replace(")","").replace("%","pct") for c in raw.columns])

# même nettoyage que le notebook
def bucket_weather(col):
    c = F.lower(F.coalesce(col, F.lit("")))
    return (F.when(c.contains("snow")|c.contains("sleet")|c.contains("wintry")|c.contains("ice"),"Snow")
             .when(c.contains("rain")|c.contains("drizzle")|c.contains("shower")|c.contains("thunder"),"Rain")
             .when(c.contains("fog")|c.contains("mist")|c.contains("haze"),"Fog")
             .when(c.contains("cloud")|c.contains("overcast"),"Cloud")
             .when(c.contains("clear")|c.contains("fair"),"Clear").otherwise("Other"))

df = raw.drop("end_lat","end_lng","wind_chill_f")
df = df.dropna(subset=["severity","start_lat","start_lng"])
df = (df.withColumn("grave",(F.col("severity")>=3).cast("int"))
        .withColumn("hour",F.hour("start_time")).withColumn("dow",F.dayofweek("start_time"))
        .withColumn("month",F.month("start_time")).withColumn("year",F.year("start_time"))
        .withColumn("is_night",(F.col("sunrise_sunset")==F.lit("Night")).cast("int"))
        .withColumn("weather_bucket",bucket_weather(F.col("weather_condition"))))
for c in INFRA:
    df = df.withColumn(c, F.coalesce(F.col(c), F.lit(False)).cast("int"))
for c in ["hour","is_night"]:
    df = df.withColumn(c, F.coalesce(F.col(c), F.lit(0)))
df = df.cache()
print(f"[{time.time()-t0:5.0f}s] nettoyage : {df.count():,} lignes", flush=True)

# échantillon d'entraînement stratifié par État
cols = INFRA + WEATHER_NUM + ["hour","dow","month","year","is_night",
                              "weather_bucket","state","grave","severity",
                              "start_lat","start_lng"]
sp = os.path.join(OUT, "accidents_sample.parquet")
if os.path.exists(sp):
    print(f"[{time.time()-t0:5.0f}s] échantillon déjà présent - sauté", flush=True)
else:
    w = Window.partitionBy("state").orderBy(F.rand(SEED))
    samp = (df.select(*cols).withColumn("_rn", F.row_number().over(w))
              .filter(F.col("_rn") <= PER_STATE_CAP).drop("_rn")).toPandas()
    samp.to_parquet(sp, index=False)
    print(f"[{time.time()-t0:5.0f}s] échantillon : {len(samp):,} lignes "
          f"({samp['state'].nunique()} États)", flush=True)

# agrégats zones H3, encodage pandas par État
import h3 as h3lib
import pandas as pd
zp = os.path.join(OUT, "zones.parquet")
if os.path.exists(zp) and os.path.exists(os.path.join(OUT, "zones_year.parquet")):
    print(f"[{time.time()-t0:5.0f}s] zones déjà présentes - recalcul quand même de zones_year si absent", flush=True)
states = [r["state"] for r in df.select("state").distinct().collect() if r["state"]]
parts = []
for i, stt in enumerate(sorted(states), 1):
    t = (df.filter(F.col("state") == stt)
           .select("start_lat","start_lng","severity",*INFRA)).toPandas()
    if t.empty:
        continue
    t["h3_cell"] = [h3lib.latlng_to_cell(a, b, 8)
                    for a, b in zip(t["start_lat"], t["start_lng"])]
    aggmap = {"severity": ["count","mean","sum"], **{e: "sum" for e in INFRA}}
    z = t.groupby("h3_cell").agg(aggmap)
    z.columns = ["n_accidents","avg_severity","charge"] + ["n_"+e for e in INFRA]
    z = z.reset_index(); z["state"] = stt
    parts.append(z)
    if i % 10 == 0 or i == len(states):
        print(f"[{time.time()-t0:5.0f}s]   zones {i}/{len(states)} États", flush=True)
zones = pd.concat(parts, ignore_index=True)
zones.to_parquet(zp, index=False)
print(f"[{time.time()-t0:5.0f}s] zones : {len(zones):,} cellules H3", flush=True)

# zones x année (pour le backtest)
parts_y = []
for i, stt in enumerate(sorted(states), 1):
    t = (df.filter(F.col("state") == stt)
           .select("start_lat","start_lng","severity","grave","year")).toPandas()
    if t.empty: continue
    t["h3_cell"] = [h3lib.latlng_to_cell(a, b, 8)
                    for a, b in zip(t["start_lat"], t["start_lng"])]
    zy = (t.groupby(["h3_cell","year"])
            .agg(n=("severity","count"), charge=("severity","sum"), graves=("grave","sum"))
            .reset_index())
    zy["state"] = stt
    parts_y.append(zy)
zones_year = pd.concat(parts_y, ignore_index=True)
zones_year.to_parquet(os.path.join(OUT, "zones_year.parquet"), index=False)
print(f"[{time.time()-t0:5.0f}s] zones x année : {len(zones_year):,} lignes", flush=True)

# tendance par territoire et par année
qa = df.groupBy("state","year").agg(F.count("*").alias("n"), F.sum("grave").alias("graves"))
qb = df.groupBy("year").agg(F.count("*").alias("n"), F.sum("grave").alias("graves")) \
       .withColumn("state", F.lit("US"))
qa.unionByName(qb).toPandas().to_parquet(os.path.join(OUT, "quand_year.parquet"), index=False)
print(f"[{time.time()-t0:5.0f}s] tendance annuelle écrite", flush=True)

# agrégats temporels par État (+ US entier)
def quand(dim):
    a = df.groupBy("state", dim).agg(F.count("*").alias("n"), F.mean("grave").alias("part_grave"))
    b = df.groupBy(dim).agg(F.count("*").alias("n"), F.mean("grave").alias("part_grave")) \
          .withColumn("state", F.lit("US"))
    return a.unionByName(b).toPandas()
quand("hour").to_parquet(os.path.join(OUT, "quand_hour.parquet"), index=False)
quand("weather_bucket").to_parquet(os.path.join(OUT, "quand_weather.parquet"), index=False)
quand("month").to_parquet(os.path.join(OUT, "quand_month.parquet"), index=False)
print(f"[{time.time()-t0:5.0f}s] agrégats QUAND écrits", flush=True)

print(f"PREP DONE en {time.time()-t0:.0f}s - artefacts dans interface/data/", flush=True)
spark.stop()
