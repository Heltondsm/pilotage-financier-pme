"""Le 5 de chaque mois : les nouveaux bilans et le nouvel annuaire, puis la comparaison avec le secteur."""
import os
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

PROJET = Path(__file__).resolve().parent.parent
PYTHON = PROJET / ".venv" / "bin" / "python"
DBT = PROJET / ".venv" / "bin" / "dbt"
CIBLE = os.environ.get("CIBLE", "local")

with DAG(
    dag_id="referentiels_mensuel",
    schedule="0 7 5 * *",                                 # le 5 du mois à 7 h (l'INSEE publie le 1er)
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Paris"),
    catchup=False,
    tags=["portfolio"],
) as dag:
    telecharger = BashOperator(task_id="telecharger_referentiels",
                               bash_command=f"cd {PROJET} && {PYTHON} telecharger_referentiels.py")
    charger = BashOperator(task_id="charger_referentiels",
                           bash_command=f"cd {PROJET} && {PYTHON} charger.py --cible {CIBLE} --referentiels")
    dbt_build = BashOperator(task_id="dbt_build",
                             bash_command=f"cd {PROJET}/dbt && {DBT} build --profiles-dir . --target {CIBLE}")

    telecharger >> charger >> dbt_build
