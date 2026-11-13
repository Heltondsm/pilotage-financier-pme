# À lancer au début de chaque séance, dans le terminal : source activer.sh
# Il active l'environnement Python du projet et donne à Airflow les bons réglages.

source .venv/bin/activate                          # le Python et les outils du projet
export AIRFLOW_HOME="$PWD/airflow"                 # où Airflow range sa base et ses journaux
export AIRFLOW__CORE__DAGS_FOLDER="$PWD/dags"      # où Airflow cherche les DAG
export AIRFLOW__CORE__LOAD_EXAMPLES=False          # sans les dizaines de DAG d'exemple

# BigQuery : enlève le # au début des 3 lignes (étape BigQuery du guide)
export GCP_PROJET="job-market-analytics-513217"
export GCP_CLE="$HOME/.cles/job-market-analytics.json"
export CIBLE="bigquery"

# Facultatif : l'assistant Gemini et l'envoi du mail. Les secrets vont dans secrets.sh
# (jamais sur GitHub, voir .gitignore) ; s'il n'existe pas, tout marche quand même.
if [ -f secrets.sh ]; then source secrets.sh; fi
