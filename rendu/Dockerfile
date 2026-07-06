# Build : docker build -t xploring-rendu .
# Run   : docker run --rm -m 10g -v "$PWD/out:/app/out" xploring-rendu

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

# Livrable + tests
COPY notebook.ipynb .
COPY tests/ tests/

# Exécution top->bottom sans intervention ; les artefacts sont copiés dans /app/out
CMD mkdir -p out \
 && jupyter nbconvert --to notebook --execute notebook.ipynb \
      --output out/notebook_executed.ipynb --ExecutePreprocessor.timeout=7200 \
 && cp -f zones_prioritaires.csv carte_zones_prioritaires.html out/ 2>/dev/null ; \
    ls -lh out/
