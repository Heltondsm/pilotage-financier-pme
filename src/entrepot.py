"""Lire une table de l'entrepôt (DuckDB ou BigQuery) en une ligne, pour les scripts de fin de chaîne."""
import os

import pandas as pd

from src import config


def lire(sql, cible="local"):
    """Exécute une requête de LECTURE ; « {schema} » est remplacé par le bon nom selon l'entrepôt."""
    if cible == "local":
        import duckdb

        # lecture seule, et aucun accès aux fichiers du Mac depuis une requête (read_csv('/…') refusé)
        base = duckdb.connect(str(config.ROOT / "entrepot.duckdb"), read_only=True,
                              config={"enable_external_access": False})
        return base.execute(sql.replace("{schema}", "pilotage")).df()
    from google.cloud import bigquery

    client = bigquery.Client.from_service_account_json(os.environ["GCP_CLE"])
    return client.query(sql.replace("{schema}", f"{client.project}.pilotage")).to_dataframe()


def euros(x):
    return f"{x:,.0f} €".replace(",", " ") if pd.notna(x) else "?"
