# Reproductibilité totale : Python 3.12 + JDK (PySpark) encapsulés.
#
# Build :  docker build -t xploring-rendu .
# Run   :  docker run --rm -m 10g -v "$PWD/out:/app/out" xploring-rendu
#          -> exécute le notebook de bout en bout (données téléchargées via kagglehub)
#             et dépose notebook exécuté + CSV + carte dans ./out
#
# Un CSV local peut être monté pour éviter le téléchargement (~3 Go) :
#          docker run --rm -m 10g -v "$PWD/out:/app/out" \
#            -v "/chemin/US_Accidents_March23.csv:/app/US_Accidents_March23.csv:ro" xploring-rendu

FROM python:3.12-slim

# JDK headless requis par PySpark ; procps fournit `ps` (utilisé par Spark)
RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless procps \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances figées (cache de layer : ne se reconstruit que si requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir nbconvert ipykernel

# Livrable + cache OSM (permet l'exposition routière hors-ligne) + tests
COPY notebook.ipynb .
COPY cache/ cache/
COPY tests/ tests/

# Exécution top->bottom sans intervention ; les artefacts sont copiés dans /app/out
CMD mkdir -p out \
 && jupyter nbconvert --to notebook --execute notebook.ipynb \
      --output out/notebook_executed.ipynb --ExecutePreprocessor.timeout=7200 \
 && cp -f zones_prioritaires.csv carte_zones_prioritaires.html out/ 2>/dev/null ; \
    ls -lh out/
