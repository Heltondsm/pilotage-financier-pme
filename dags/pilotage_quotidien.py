"""Chaque nuit à 6 h : le Bodacc, la journée de Distrimat, l'entrepôt, dbt (avec ses tests), puis l'alerte."""
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
    dag_id="pilotage_quotidien",
    schedule="0 6 * * *",
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Paris"),
    catchup=False,
    tags=["portfolio"],
) as dag:
    bodacc = BashOperator(task_id="collecter_bodacc", bash_command=f"cd {PROJET} && {PYTHON} collecter_bodacc.py")
    simuler = BashOperator(task_id="simuler_la_journee", bash_command=f"cd {PROJET} && {PYTHON} simuler.py")
    charger = BashOperator(task_id="charger", bash_command=f"cd {PROJET} && {PYTHON} charger.py --cible {CIBLE}")
    dbt_build = BashOperator(task_id="dbt_build",
                             bash_command=f"cd {PROJET}/dbt && {DBT} build --profiles-dir . --target {CIBLE}")
    alerter = BashOperator(task_id="alerter", bash_command=f"cd {PROJET} && {PYTHON} alerter.py --cible {CIBLE}")

    bodacc >> simuler >> charger >> dbt_build >> alerter     # le Bodacc d'abord : un client en procédure ne paie plus
