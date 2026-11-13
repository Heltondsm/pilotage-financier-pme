"""Chaque nuit : collecter les annonces légales (Bodacc, données réelles) des clients et fournisseurs de Distrimat.

La première fois, on remonte 2 ans en arrière ; ensuite, on ne lit que les annonces récentes
(depuis la dernière collecte, avec 7 jours de marge). Résultat : data/bodacc_AAAA-MM-JJ.csv

    python collecter_bodacc.py
"""
import csv
import json
import time
from datetime import date, timedelta

from src import config
from src.api import lire_json

FAMILLES = ["collective", "conciliation", "radiation", "vente", "modification", "dpc"]
PAR_LOT = 40                                     # nombre de SIREN demandés en une fois


def sirens_du_portefeuille():
    """Les vrais SIREN des clients et fournisseurs (fichier privé, jamais publié)."""
    with open(config.SIMU_DIR / "correspondance_siren.csv", encoding="utf-8") as f:
        return sorted({ligne["siren"] for ligne in csv.DictReader(f)})


def date_de_depart():
    """2 ans en arrière la première fois ; sinon la dernière collecte moins 7 jours.
    Le fichier du jour ne compte pas : relancer le même jour refait la même collecte."""
    fichiers = sorted(f for f in config.DATA_DIR.glob("bodacc_*.csv") if f.stem < f"bodacc_{date.today()}")
    if not fichiers:
        return date.today() - timedelta(days=730)
    derniere = date.fromisoformat(fichiers[-1].stem.replace("bodacc_", ""))
    return derniere - timedelta(days=7)


def lire_json_texte(texte):
    """Certains champs du Bodacc sont du JSON écrit dans un texte."""
    try:
        return json.loads(texte) if texte else {}
    except (TypeError, ValueError):
        return {}


def aplatir(a, portefeuille=frozenset()):
    """Une annonce -> une ligne de CSV, avec les informations utiles sorties du JSON."""
    jugement = lire_json_texte(a.get("jugement"))
    depot = lire_json_texte(a.get("depot"))
    modif = lire_json_texte(a.get("modificationsgenerales"))
    sirens = [r for r in (a.get("registre") or []) if r.isdigit() and len(r) == 9]
    # une annonce peut citer plusieurs SIREN (une fusion) : on garde celui du portefeuille
    sirens = sorted(sirens, key=lambda s: s not in portefeuille)
    return {
        "id_annonce": a["id"],
        "siren": sirens[0] if sirens else "",
        "date_parution": a.get("dateparution") or "",
        "famille": a.get("familleavis") or "",
        "famille_libelle": a.get("familleavis_lib") or "",
        "type_avis": a.get("typeavis_lib") or "",
        "nom": (a.get("commercant") or "")[:80],
        "tribunal": (a.get("tribunal") or "")[:80],
        "departement": a.get("numerodepartement") or "",
        "jugement_famille": jugement.get("famille") or "",
        "jugement_nature": (jugement.get("nature") or "")[:120],
        "jugement_date": jugement.get("date") or "",
        "depot_date_cloture": depot.get("dateCloture") or "",
        "modification": (modif.get("descriptif") or "")[:200],
    }


def main():
    sirens = sirens_du_portefeuille()
    depart = date_de_depart()
    print(f"{len(sirens)} SIREN, annonces depuis le {depart}")
    lignes, vues = [], set()
    for i in range(0, len(sirens), PAR_LOT):
        lot = sirens[i:i + PAR_LOT]
        filtre = (f'dateparution >= "{depart}" and familleavis in ({", ".join(chr(34) + f + chr(34) for f in FAMILLES)})'
                  f' and ({" or ".join(f"registre={chr(34)}{s}{chr(34)}" for s in lot)})')
        annonces = lire_json(config.URL_BODACC.replace("/records", "/exports/json"), {"where": filtre})
        for a in annonces:
            if a["id"] not in vues:                 # une annonce ne compte qu'une fois
                vues.add(a["id"])
                lignes.append(aplatir(a, set(lot)))
        time.sleep(0.3)
    sortie = config.DATA_DIR / f"bodacc_{date.today()}.csv"
    with open(sortie, "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(aplatir({"id": ""}).keys()), lineterminator="\n")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    familles = {}
    for l in lignes:
        familles[l["famille_libelle"]] = familles.get(l["famille_libelle"], 0) + 1
    print(f"{len(lignes)} annonces écrites dans {sortie.name} :", familles)


if __name__ == "__main__":
    main()
