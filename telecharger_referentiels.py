"""Chaque mois : télécharger les deux référentiels publics.

1. les bilans de toutes les entreprises (ratios INPI / BCE, ~7 millions de lignes, format Parquet) ;
2. l'annuaire des entreprises (Sirene, ~30 millions d'entreprises), allégé : on garde seulement les
   entreprises actives qui ont au moins un bilan, et 6 colonnes utiles.

    python telecharger_referentiels.py
Résultat : data/referentiels/bilans.parquet et data/referentiels/entreprises.parquet
"""
import json
import shutil
import urllib.request

import duckdb

from src import config


def telecharger(url, destination):
    """Télécharge un gros fichier par morceaux, sans tout mettre en mémoire."""
    temporaire = destination.with_suffix(".part")
    requete = urllib.request.Request(url, headers={"User-Agent": "pilotage-pme/1.0"})
    with urllib.request.urlopen(requete, timeout=600) as reponse, open(temporaire, "wb") as fichier:
        shutil.copyfileobj(reponse, fichier, length=1024 * 1024)
    temporaire.rename(destination)                      # le fichier n'est remplacé que s'il est complet
    print(f"{destination.name} : {destination.stat().st_size / 1e6:.0f} Mo")


def url_sirene():
    """L'adresse du dernier fichier Sirene « StockUniteLegale » au format Parquet."""
    with urllib.request.urlopen(config.URL_JEU_SIRENE, timeout=60) as reponse:
        jeu = json.loads(reponse.read())
    for ressource in jeu["resources"]:
        if ressource["title"].startswith("Sirene : Fichier StockUniteLegale - ") and ressource["format"] == "parquet":
            return ressource["url"]
    raise RuntimeError("fichier Sirene introuvable sur data.gouv.fr")


def main():
    bilans = config.REF_DIR / "bilans.parquet"
    sirene_complet = config.REF_DIR / "sirene_complet.parquet"
    telecharger(config.URL_BILANS_PARQUET, bilans)      # 700 Mo : 5 à 15 minutes selon la connexion
    telecharger(url_sirene(), sirene_complet)           # 700 Mo aussi

    # l'annuaire allégé : 30 millions de lignes -> les seules entreprises utiles
    base = duckdb.connect()
    base.execute(f"""
        copy (
            select
                s.siren,
                coalesce(s.denominationUniteLegale, s.nomUniteLegale) as nom,
                s.activitePrincipaleUniteLegale                        as naf,
                s.trancheEffectifsUniteLegale                          as tranche_effectif,
                s.categorieEntreprise                                  as categorie,
                s.dateCreationUniteLegale                              as date_creation
            from '{sirene_complet}' s
            where s.etatAdministratifUniteLegale = 'A'              -- entreprises actives
              and s.siren in (select distinct siren from '{bilans}') -- qui ont publié au moins un bilan
        ) to '{config.REF_DIR / "entreprises.parquet"}' (format parquet)
    """)
    nb = base.execute(f"select count(*) from '{config.REF_DIR / 'entreprises.parquet'}'").fetchone()[0]
    sirene_complet.unlink()                              # 700 Mo de moins sur le disque
    print(f"entreprises.parquet : {nb} entreprises actives avec au moins un bilan")


if __name__ == "__main__":
    main()
