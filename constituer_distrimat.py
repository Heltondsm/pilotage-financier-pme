"""Une seule fois : fabriquer Distrimat, l'entreprise FICTIVE de démonstration.

1. son profil : ses chiffres clés sont la MÉDIANE RÉELLE de ses concurrents (grossistes en matériaux
   de construction de 50 à 99 salariés), lue dans les bilans publics ;
2. ses clients : de vraies entreprises du bâtiment d'Île-de-France, affichées seulement sous un code
   (« C0001 ») ; le lien entre le code et le vrai SIREN reste dans data/ et ne part jamais sur GitHub ;
3. ses fournisseurs : de vrais fabricants de matériaux, eux aussi sous un code ;
4. son catalogue de produits (fictif) et le budget de l'année.

    python constituer_distrimat.py
"""
import csv
import json
import random
import time

import duckdb

from src import config
from src.api import lire_json

FAMILLES = [  # famille de produits, part des ventes, marge brute de la famille (avant calage)
    ("Ciment et béton", 0.20, 0.22), ("Plâtre et cloisons", 0.15, 0.26), ("Isolation", 0.14, 0.30),
    ("Bois et panneaux", 0.13, 0.28), ("Carrelage et sols", 0.12, 0.34), ("Couverture et toiture", 0.10, 0.27),
    ("Outillage", 0.08, 0.38), ("Quincaillerie", 0.08, 0.42),
]


def profil_secteur():
    """La médiane des concurrents réels, sur leur dernier bilan complet (exercice 2023 ou plus récent)."""
    base = duckdb.connect()
    requete = f"""
        with dernier as (
            select b.*, row_number() over (partition by b.siren order by b.date_cloture_exercice desc) as rang
            from '{config.REF_DIR / "bilans.parquet"}' b
            join '{config.REF_DIR / "entreprises.parquet"}' e using (siren)
            where e.naf = '{config.NAF_DISTRIMAT}'
              and e.tranche_effectif in ({", ".join(repr(t) for t in config.TRANCHES_PAIRS)})
              and b.date_cloture_exercice >= '2023-01-01'
              and b.chiffre_d_affaires > 0 and b.marge_brute > 0    -- comptes complets (pas confidentiels)
        )
        select count(*)                                                  as nb_pairs,
               median(chiffre_d_affaires)                                as chiffre_affaires,
               median(marge_brute / chiffre_d_affaires)                  as taux_marge_brute,
               median(marge_ebe) / 100                                   as taux_ebe,
               median(credit_clients_jours)                              as delai_clients_jours,
               median(credit_fournisseurs_jours)                         as delai_fournisseurs_jours,
               median(rotation_des_stocks_jours)                         as stock_jours
        from dernier where rang = 1
    """
    profil = base.execute(requete).df().iloc[0].to_dict()
    return {k: (int(v) if k == "nb_pairs" else round(float(v), 4)) for k, v in profil.items()}


def chercher(naf, departement, tranches, pages):
    trouvees = []
    for page in range(1, pages + 1):
        params = {"activite_principale": naf, "etat_administratif": "A", "tranche_effectif_salarie": tranches,
                  "per_page": 25, "page": page}
        if departement:
            params["departement"] = departement
        reponse = lire_json(config.URL_ENTREPRISES, params)
        trouvees += reponse["results"]
        time.sleep(0.2)
        if page >= reponse["total_pages"]:
            break
    return trouvees


def main():
    hasard = random.Random(config.GRAINE)
    profil = profil_secteur()
    print("profil du secteur :", profil)

    # --- les clients : de vraies entreprises du bâtiment d'Île-de-France
    candidats = {}
    for naf in config.NAF_CLIENTS:
        for dep in config.DEPARTEMENTS_IDF:
            for e in chercher(naf, dep, "01,02,03,11,12", pages=1):
                cp = (e.get("siege") or {}).get("code_postal") or ""
                if cp[:2] in config.DEPARTEMENTS_IDF:       # l'API renvoie aussi les sièges hors IDF qui ont un chantier ici
                    candidats[e["siren"]] = (e["activite_principale"], cp)
    sirens = hasard.sample(sorted(candidats), min(config.NB_CLIENTS, len(candidats)))
    clients, correspondance = [], []
    for i, siren in enumerate(sirens, 1):
        naf, cp = candidats[siren]
        code = f"C{i:04d}"
        clients.append({"code_client": code, "activite": naf, "departement": cp[:2],
                        "date_premiere_commande": f"{hasard.choice([2019, 2020, 2021, 2022, 2023])}-{hasard.randint(1, 12):02d}-01"})
        correspondance.append({"code": code, "siren": siren})

    # --- les fournisseurs : de vrais fabricants (toute la France)
    fournisseurs_candidats = {}
    for naf in config.NAF_FOURNISSEURS:
        for e in chercher(naf, None, "11,12,21,22,31,32", pages=2):
            fournisseurs_candidats[e["siren"]] = e["activite_principale"]
    sirens_f = hasard.sample(sorted(fournisseurs_candidats), min(config.NB_FOURNISSEURS, len(fournisseurs_candidats)))
    fournisseurs = []
    for i, siren in enumerate(sirens_f, 1):
        code = f"F{i:03d}"
        fournisseurs.append({"code_fournisseur": code, "activite": fournisseurs_candidats[siren]})
        correspondance.append({"code": code, "siren": siren})

    # --- le catalogue : 8 familles, 15 produits chacune ; les marges sont recalées sur celle du secteur
    moyenne = sum(part * marge for _, part, marge in FAMILLES)
    facteur = profil["taux_marge_brute"] / moyenne
    produits = []
    for f, (famille, part, marge) in enumerate(FAMILLES, 1):
        for p in range(1, 16):
            prix = round(hasard.lognormvariate(3.3, 0.8), 2)           # ~27 € en médiane
            produits.append({"code_produit": f"P{f}{p:02d}", "famille": famille, "prix_vente_ht": prix,
                             "taux_marge": round(min(0.6, marge * facteur * hasard.uniform(0.85, 1.15)), 3),
                             "poids_famille": part})

    def ecrire(nom, lignes):
        with open(config.SEEDS_DIR / nom, "w", newline="", encoding="utf-8") as f:
            ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0]), lineterminator="\n")
            ecrivain.writeheader()
            ecrivain.writerows(lignes)
        print(f"{nom} : {len(lignes)} lignes")

    ecrire("clients.csv", clients)
    ecrire("fournisseurs.csv", fournisseurs)
    ecrire("produits.csv", produits)
    # la correspondance code -> vrai SIREN : seulement dans data/ (ignoré par Git)
    with open(config.SIMU_DIR / "correspondance_siren.csv", "w", newline="", encoding="utf-8") as f:
        ecrivain = csv.DictWriter(f, fieldnames=["code", "siren"], lineterminator="\n")
        ecrivain.writeheader()
        ecrivain.writerows(correspondance)
    (config.SIMU_DIR / "profil_secteur.json").write_text(json.dumps(profil, indent=1), encoding="utf-8")
    print("profil_secteur.json et correspondance_siren.csv écrits dans data/distrimat/")


if __name__ == "__main__":
    main()
