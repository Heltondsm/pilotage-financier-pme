"""Ranger les données dans l'entrepôt (DuckDB sur le Mac, ou BigQuery).

    python charger.py --cible local                    -> chaque nuit : Distrimat + Bodacc
    python charger.py --cible local --referentiels     -> chaque mois : en plus, les bilans et l'annuaire

Tout est REMPLACÉ à chaque chargement : Distrimat est recalculé en entier, les annonces sont relues
dans tous les fichiers du Bodacc collectés, les référentiels sont remplacés chaque mois. Relancer le
script deux fois de suite donne donc le même résultat.
"""
import argparse
import os
from datetime import date

import pandas as pd

from src import config


def tables_du_jour(referentiels):
    """{nom de la table : (tableau, mode)} ; mode = « remplacer » ou « ajouter »."""
    t = {nom: (pd.read_parquet(config.SIMU_DIR / f"{nom}.parquet"), "remplacer")
         for nom in ["factures", "paiements", "achats", "charges"]}
    t["correspondance"] = (pd.read_csv(config.SIMU_DIR / "correspondance_siren.csv", dtype=str), "remplacer")
    lots = []                                   # TOUTES les collectes du Bodacc (chacune ne lit que les jours récents)
    for fichier in sorted(config.DATA_DIR.glob("bodacc_*.csv")):
        lot = pd.read_csv(fichier, dtype=str, keep_default_na=False)
        lot["date_collecte"] = date.fromisoformat(fichier.stem.split("_")[1])
        lots.append(lot)
    if lots:
        t["annonces"] = (pd.concat(lots, ignore_index=True), "remplacer")   # dbt retire les doublons
    if referentiels:
        t["bilans"] = (config.REF_DIR / "bilans.parquet", "remplacer")             # trop gros pour pandas :
        t["entreprises"] = (config.REF_DIR / "entreprises.parquet", "remplacer")   # on charge le fichier directement
    return t


def charger_local(tables):
    import duckdb

    base = duckdb.connect(str(config.ROOT / "entrepot.duckdb"))
    base.execute("create schema if not exists brut")
    for nom, (donnees, mode) in tables.items():
        source = f"read_parquet('{donnees}')" if not isinstance(donnees, pd.DataFrame) else "donnees"
        if mode == "remplacer":
            base.execute(f"create or replace table brut.{nom} as select * from {source}")
        else:
            base.execute(f"create table if not exists brut.{nom} as select * from {source} limit 0")
            base.execute(f"insert into brut.{nom} by name select * from {source}")
        print(f"  brut.{nom} : {base.execute(f'select count(*) from brut.{nom}').fetchone()[0]} lignes")


def charger_bigquery(tables):
    from google.cloud import bigquery

    client = bigquery.Client.from_service_account_json(os.environ["GCP_CLE"])
    jeu = bigquery.Dataset(f"{client.project}.pilotage_brut")
    jeu.location = "EU"
    client.create_dataset(jeu, exists_ok=True)
    for nom, (donnees, mode) in tables.items():
        cible = f"{client.project}.pilotage_brut.{nom}"
        reglages = bigquery.LoadJobConfig(
            write_disposition="WRITE_TRUNCATE" if mode == "remplacer" else "WRITE_APPEND",
            source_format=bigquery.SourceFormat.PARQUET)
        if isinstance(donnees, pd.DataFrame):
            client.load_table_from_dataframe(donnees, cible, job_config=reglages).result()
        else:
            with open(donnees, "rb") as fichier:
                client.load_table_from_file(fichier, cible, job_config=reglages).result()
        print(f"  {cible} : {client.get_table(cible).num_rows} lignes")


if __name__ == "__main__":
    parametres = argparse.ArgumentParser()
    parametres.add_argument("--cible", choices=["local", "bigquery"], default="local")
    parametres.add_argument("--referentiels", action="store_true", help="charger aussi les bilans et l'annuaire")
    options = parametres.parse_args()
    tables = tables_du_jour(options.referentiels)
    (charger_local if options.cible == "local" else charger_bigquery)(tables)
