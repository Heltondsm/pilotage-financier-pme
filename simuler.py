"""Chaque nuit : reconstituer l'activité de Distrimat jusqu'à hier (données de TEST).

L'historique ne bouge pas : chaque jour et chaque facture ont leur propre hasard, fixé par la graine.
Relancer le script redonne exactement les mêmes chiffres, et chaque nuit ajoute seulement le nouveau
jour. Les totaux de chaque année retombent sur la médiane réelle du secteur
(data/distrimat/profil_secteur.json).

Les clients en procédure au Bodacc (vraies annonces) ne sont plus livrés à partir de la publication
(le jour où Distrimat l'apprend), et ne paient plus ce qui arrive à échéance après le jugement.

    python simuler.py                   (jusqu'à hier)
    python simuler.py 2026-06-30        (jusqu'à une date donnée : sert à vérifier que l'historique ne bouge pas)
Résultat dans data/distrimat/ : factures.parquet, paiements.parquet, achats.parquet, charges.parquet,
et, dans dbt/seeds : budget.csv et parametres.csv
"""
import csv
import glob
import json
import math
import random
import sys
import zlib
from datetime import date, timedelta

import pandas as pd

from src import config

SAISON = [0.85, 0.9, 1.05, 1.1, 1.1, 1.1, 1.05, 0.6, 1.05, 1.1, 1.0, 0.8]   # le bâtiment ralentit en août et en décembre
SAISON = [s * 12 / sum(SAISON) for s in SAISON]
CROISSANCE = 0.03                       # +3 % par an
TVA = 0.20
DELAI_CONTRACTUEL = 45                  # paiement à 45 jours (ce que prévoit la facture)
ANNEE_CALAGE_DSO = 2025                 # l'année (fixe) sur laquelle on cale le délai de paiement des clients


def hasard_de(*cle):
    """Un tirage au hasard propre à une clé (un jour, une facture) : il ne dépend de rien d'autre."""
    return random.Random(f"{config.GRAINE}-" + "-".join(str(c) for c in cle))


def empreinte(*cle):
    """Un nombre fixe entre 0 et 999 pour une clé : sert à choisir les défauts de qualité, toujours les mêmes."""
    return zlib.crc32("-".join(str(c) for c in cle).encode()) % 1000


def lire_csv(chemin):
    with open(chemin, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def procedures_bodacc():
    """{code_client: (date du jugement, date de publication)} pour les jugements graves (vraies annonces)."""
    fichiers = sorted(glob.glob(str(config.DATA_DIR / "bodacc_*.csv")))
    if not fichiers:
        return {}
    siren_vers_code = {l["siren"]: l["code"] for l in lire_csv(config.SIMU_DIR / "correspondance_siren.csv")}
    annonces = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in fichiers]).drop_duplicates("id_annonce")
    graves = annonces[annonces["jugement_nature"].str.contains("liquidation|redressement", case=False)
                      & ~annonces["jugement_nature"].str.contains("rétractation|plan de", case=False)].copy()
    graves["parution"] = pd.to_datetime(graves["date_parution"], errors="coerce")
    graves["jugement"] = pd.to_datetime(graves["jugement_date"].where(graves["jugement_date"] != "", graves["date_parution"]),
                                        errors="coerce")
    premieres = graves.dropna(subset=["parution", "jugement"]).groupby("siren")[["jugement", "parution"]].min()
    return {siren_vers_code[s]: (l.jugement.date(), l.parution.date()) for s, l in premieres.iterrows() if s in siren_vers_code}


def factures_du_jour(jour, clients, poids_client, remise, produits, poids_produit, profil):
    """Les lignes de factures d'un jour ouvré, tirées avec le hasard propre à ce jour."""
    h = hasard_de("factures", jour)
    annee = jour.year - config.DEBUT_SIMULATION.year
    ca_du_jour = profil["chiffre_affaires"] * (1 + CROISSANCE) ** annee / 252 * SAISON[jour.month - 1]
    lignes = []
    for n in range(1, max(1, int(h.gauss(ca_du_jour / 1500, math.sqrt(ca_du_jour / 1500)))) + 1):   # ~1 500 € par facture
        c = h.choices(range(len(clients)), weights=poids_client)[0]
        for _ in range(h.choice([1, 1, 2, 2, 3, 4, 5])):
            p = h.choices(range(len(produits)), weights=poids_produit)[0]
            lignes.append({"numero_facture": f"FA{jour:%Y%m%d}-{n:03d}", "date_facture": jour,
                           "code_client": clients[c]["code_client"], "code_produit": produits[p]["code_produit"],
                           "quantite": max(1, int(h.lognormvariate(2.6, 0.9))),
                           "prix_unitaire_ht": round(float(produits[p]["prix_vente_ht"]) * (1 - remise[c]), 2),
                           "idx_client": c})
    return lignes


def main():
    hasard = random.Random(config.GRAINE)
    profil = json.loads((config.SIMU_DIR / "profil_secteur.json").read_text(encoding="utf-8"))
    clients = lire_csv(config.SEEDS_DIR / "clients.csv")
    produits = lire_csv(config.SEEDS_DIR / "produits.csv")
    fournisseurs = lire_csv(config.SEEDS_DIR / "fournisseurs.csv")
    procedures = procedures_bodacc()
    hier = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today() - timedelta(days=1)

    # --- le comportement de chaque client (fixé une fois pour toutes par la graine)
    poids_client = [hasard.paretovariate(1.6) for _ in clients]                  # quelques gros clients, beaucoup de petits
    retard = []                                                                  # jours de retard habituels
    for _ in clients:
        r = hasard.random()
        retard.append(hasard.gauss(0, 4) if r < 0.7 else hasard.uniform(10, 30) if r < 0.9 else hasard.uniform(30, 90))
    remise = [hasard.choice([0, 0, 0.03, 0.05, 0.08, 0.12]) for _ in clients]
    poids_produit = [float(p["poids_famille"]) for p in produits]
    poids_f = [hasard.paretovariate(1.4) for _ in fournisseurs]

    # --- les factures, jour par jour, jusqu'au 31 décembre (pour caler l'année entière)
    lignes, jour = [], config.DEBUT_SIMULATION
    while jour <= date(hier.year, 12, 31):
        if jour.weekday() < 5:                                                   # du lundi au vendredi
            lignes += factures_du_jour(jour, clients, poids_client, remise, produits, poids_produit, profil)
        jour += timedelta(days=1)
    factures = pd.DataFrame(lignes)

    # --- calage : chaque année entière retombe sur la médiane du secteur (avec la croissance)
    for annee, groupe in factures.groupby(pd.to_datetime(factures["date_facture"]).dt.year):
        cible = profil["chiffre_affaires"] * (1 + CROISSANCE) ** (annee - config.DEBUT_SIMULATION.year)
        facteur = cible / (groupe["quantite"] * groupe["prix_unitaire_ht"]).sum()
        factures.loc[groupe.index, "prix_unitaire_ht"] = (groupe["prix_unitaire_ht"] * facteur).round(2)
    factures["montant_ht"] = (factures["quantite"] * factures["prix_unitaire_ht"]).round(2)
    factures["date_echeance"] = factures["date_facture"] + timedelta(days=DELAI_CONTRACTUEL)

    # on ne garde que le passé, et plus aucune livraison à un client dont la procédure est publiée
    factures = factures[factures["date_facture"] <= hier]
    publiee = factures["code_client"].map(lambda c: procedures[c][1] if c in procedures else date.max)
    factures = factures[factures["date_facture"] <= publiee].reset_index(drop=True)

    # --- les paiements : un par facture, à la date prévue + le retard habituel du client
    entetes = factures.groupby("numero_facture").agg(date_facture=("date_facture", "first"),
                                                     code_client=("code_client", "first"), idx_client=("idx_client", "first"),
                                                     montant_ht=("montant_ht", "sum")).reset_index()

    def jours_avant_paiement(f, decalage):
        """Dans combien de jours la facture f est payée (None : jamais). Hasard propre à la facture."""
        h = hasard_de("paiement", f.numero_facture)
        jours = max(0, DELAI_CONTRACTUEL + retard[f.idx_client] + decalage + h.gauss(0, 6))
        if h.random() < 0.01:                                                # 1 % de litiges :
            if h.random() < 0.3:
                return None                                                  # 3 sur 10 ne sont jamais payés
            jours += h.uniform(120, 240)                                     # les autres, 4 à 8 mois plus tard
        return round(jours)

    def dso_de_l_annee(decalage):
        """Le DSO moyen des 12 fins de mois de l'année de calage, calculé comme dans dbt."""
        e = entetes[pd.to_datetime(entetes["date_facture"]).dt.year.between(ANNEE_CALAGE_DSO - 1, ANNEE_CALAGE_DSO)].copy()
        delais = [jours_avant_paiement(f, decalage) for f in e.itertuples()]
        e["paye_le"] = [pd.Timestamp(f.date_facture) + pd.Timedelta(days=d) if d is not None else pd.NaT
                        for f, d in zip(e.itertuples(), delais)]
        e["date_facture"] = pd.to_datetime(e["date_facture"])
        e["ttc"] = e["montant_ht"] * (1 + TVA)
        valeurs = []
        for fin_mois in pd.date_range(f"{ANNEE_CALAGE_DSO}-01-31", periods=12, freq="ME"):
            ouvertes = e[(e["date_facture"] <= fin_mois) & (e["paye_le"].isna() | (e["paye_le"] > fin_mois))
                         & (e["date_facture"] > fin_mois - pd.Timedelta(days=365 + DELAI_CONTRACTUEL))]
            ventes = e[(e["date_facture"] > fin_mois - pd.Timedelta(days=91)) & (e["date_facture"] <= fin_mois)]["ttc"].sum()
            valeurs.append(91 * ouvertes["ttc"].sum() / ventes)
        return sum(valeurs) / len(valeurs)

    # on ajuste le comportement des clients, une fois, sur une année fixe, jusqu'à retrouver le DSO du secteur
    decalage = 0.0
    for _ in range(6):
        ecart = profil["delai_clients_jours"] - dso_de_l_annee(decalage)
        if abs(ecart) < 0.3:
            break
        decalage += ecart
    print(f"DSO calé sur {ANNEE_CALAGE_DSO} : {dso_de_l_annee(decalage):.1f} jours (secteur : {profil['delai_clients_jours']:.1f})")

    paiements = []
    for f in entetes.itertuples():
        jours = jours_avant_paiement(f, decalage)
        if jours is None:
            continue
        procedure = procedures.get(f.code_client)
        if procedure and f.date_facture + timedelta(days=DELAI_CONTRACTUEL) > procedure[0]:
            continue                                                         # dette gelée par le jugement : pas payée
        quand = f.date_facture + timedelta(days=jours)
        if quand <= hier:
            paiements.append({"numero_paiement": "RG" + f.numero_facture[2:], "numero_facture": f.numero_facture,
                              "date_paiement": quand, "montant_ttc": round(f.montant_ht * (1 + TVA), 2)})
    paiements = pd.DataFrame(paiements)

    # --- les achats aux fournisseurs : chaque jour de vente, le coût des marchandises vendues
    achats = []
    for jour_achat, ca in factures.groupby("date_facture")["montant_ht"].sum().items():
        h = hasard_de("achat", jour_achat)
        fo = h.choices(range(len(fournisseurs)), weights=poids_f)[0]
        paye = jour_achat + timedelta(days=round(max(0, profil["delai_fournisseurs_jours"] + h.gauss(0, 8))))
        achats.append({"numero_achat": f"AC{jour_achat:%Y%m%d}", "date_achat": jour_achat,
                       "code_fournisseur": fournisseurs[fo]["code_fournisseur"],
                       "montant_ht": round(ca * (1 - profil["taux_marge_brute"]), 2),
                       "date_paiement": paye if paye <= hier else None})
    achats = pd.DataFrame(achats)

    # --- les charges fixes (salaires, loyers…) : ce qui sépare la marge brute de l'EBE, payées en fin de mois
    ca_mois = factures.groupby(pd.to_datetime(factures["date_facture"]).dt.to_period("M"))["montant_ht"].sum()
    charges = [{"mois": str(m), "montant": round(ca * (profil["taux_marge_brute"] - profil["taux_ebe"]), 2)}
               for m, ca in ca_mois.items()]

    # --- le budget : chaque mois, les ventes du même mois l'an dernier + 5 %, par famille de produits
    familles = {p["code_produit"]: p["famille"] for p in produits}
    factures["famille"] = factures["code_produit"].map(familles)
    reel = factures.groupby([pd.to_datetime(factures["date_facture"]).dt.to_period("M"), "famille"])["montant_ht"].sum()
    budget = [{"mois": str(m + 12), "famille": fam, "budget_ht": round(v * 1.05, 2)}
              for (m, fam), v in reel.items() if (m + 12).year <= hier.year]

    # --- quelques vrais défauts de qualité, comme dans un vrai logiciel de gestion (toujours les mêmes lignes)
    cle = factures["numero_facture"] + factures["code_produit"]
    doublons = factures[cle.map(lambda k: empreinte("doublon", k) < 4)]                       # ~0,4 % de lignes en double
    inconnus = factures[cle.map(lambda k: empreinte("inconnu", k) < 2)].assign(code_client="C9999")   # ~0,2 %
    factures = pd.concat([factures, doublons, inconnus], ignore_index=True)
    orphelins = paiements[paiements["numero_facture"].map(lambda k: empreinte("orphelin", k) < 1)]
    orphelins = orphelins.assign(numero_facture="FA00000000-000",                              # ~0,1 % de paiements
                                 numero_paiement=orphelins["numero_paiement"] + "-X")           # sans facture
    paiements = pd.concat([paiements, orphelins], ignore_index=True)

    sortie = config.SIMU_DIR
    factures.drop(columns=["idx_client", "famille", "montant_ht"]).to_parquet(sortie / "factures.parquet", index=False)
    paiements.to_parquet(sortie / "paiements.parquet", index=False)
    achats.to_parquet(sortie / "achats.parquet", index=False)
    pd.DataFrame(charges).to_parquet(sortie / "charges.parquet", index=False)
    pd.DataFrame(budget).to_csv(config.SEEDS_DIR / "budget.csv", index=False)
    pd.DataFrame([{"tresorerie_initiale": round(profil["chiffre_affaires"] * 0.08, 2),       # ~1 mois de ventes
                   "date_debut": str(config.DEBUT_SIMULATION), "delai_contractuel_jours": DELAI_CONTRACTUEL,
                   "taux_tva": TVA, "ca_secteur": profil["chiffre_affaires"], "croissance": CROISSANCE,
                   "nb_pairs": profil["nb_pairs"]}]).to_csv(config.SEEDS_DIR / "parametres.csv", index=False)
    print(f"{entetes.shape[0]} factures ({len(factures)} lignes), {len(paiements)} paiements, {len(achats)} achats, "
          f"{len(procedures)} clients en procédure (Bodacc), jusqu'au {hier}")


if __name__ == "__main__":
    main()
