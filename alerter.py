"""Chaque matin : la page d'alerte du DAF (et un mail si les réglages SMTP sont là).

    python alerter.py --cible local
Résultat : data/alerte_AAAA-MM-JJ.html
"""
import argparse
import html
import os
import smtplib
from datetime import date
from email.message import EmailMessage

import pandas as pd

from src import config
from src.entrepot import euros, lire


def resume(kpi, alertes, prevision):
    """Le résumé en 3 phrases, écrit par une règle simple (pas besoin d'IA pour ça)."""
    dernier = kpi.iloc[-1]
    phrases = [f"Ce mois-ci : {euros(dernier['ca_ht'])} de ventes, "
               + (f"{dernier['ecart_budget_pct']:+.1f} % par rapport au budget." if dernier["ecart_budget_pct"] == dernier["ecart_budget_pct"]
                  else "pas de budget pour ce mois.")]
    if len(alertes):
        a = alertes.iloc[0]
        phrases.append(f"{len(alertes)} client(s) à surveiller, dont {a['code_client']} ({euros(a['encours_ttc'])} dus) : {a['action']}.")
    else:
        phrases.append("Aucun client à surveiller en urgence.")
    bas = prevision.loc[prevision["solde_prevu"].idxmin()]
    phrases.append(f"Trésorerie : point le plus bas prévu le {bas['jour']:%d/%m} à {euros(bas['solde_prevu'])}.")
    return phrases


def texte(x):
    """Une case vide plutôt que « nan » ou « <NA> » quand la valeur manque."""
    return "" if pd.isna(x) else html.escape(str(x))


def page(phrases, alertes):
    lignes = "".join(f"<tr><td>{texte(a.code_client)}</td><td>{euros(a.encours_ttc)}</td><td>{texte(a.retard_max_jours)}</td>"
                     f"<td>{texte(a.procedure_bodacc)}</td><td>{texte(a.action)}</td></tr>"
                     for a in alertes.itertuples()) or "<tr><td colspan='5'>Rien à signaler.</td></tr>"
    return f"""<html><body style="font-family:Arial,sans-serif;color:#1d2433">
<h2>Distrimat : le point du {date.today():%d/%m/%Y} (données de test)</h2>
<p style="background:#eef3fb;padding:12px;border-left:4px solid #376dae">{"<br>".join(html.escape(p) for p in phrases)}</p>
<h3>Les clients à surveiller</h3>
<table border="1" cellpadding="6" style="border-collapse:collapse">
<tr><th>Client</th><th>Dû</th><th>Retard max (jours)</th><th>Procédure (Bodacc)</th><th>Action</th></tr>{lignes}</table>
</body></html>"""


def envoyer(contenu):
    reglages = {k: os.environ.get(k) for k in ("SMTP_SERVEUR", "SMTP_UTILISATEUR", "SMTP_MOT_DE_PASSE", "ALERTE_DESTINATAIRE")}
    if not all(reglages.values()):
        print("Pas de réglages SMTP : la page reste dans data/, sans envoi.")
        return
    mail = EmailMessage()
    mail["Subject"], mail["From"], mail["To"] = f"Distrimat : le point du {date.today():%d/%m}", reglages["SMTP_UTILISATEUR"], reglages["ALERTE_DESTINATAIRE"]
    mail.set_content("Ouvre ce mail en HTML.")
    mail.add_alternative(contenu, subtype="html")
    with smtplib.SMTP_SSL(reglages["SMTP_SERVEUR"], 465) as serveur:
        serveur.login(reglages["SMTP_UTILISATEUR"], reglages["SMTP_MOT_DE_PASSE"])
        serveur.send_message(mail)
    print("Alerte envoyée.")


if __name__ == "__main__":
    options = argparse.ArgumentParser()
    options.add_argument("--cible", choices=["local", "bigquery"], default="local")
    cible = options.parse_args().cible
    kpi = lire("select * from {schema}.kpi_mensuels order by mois", cible)
    alertes = lire("select * from {schema}.alertes_clients order by encours_ttc desc", cible)
    prevision = lire("select * from {schema}.prevision_tresorerie order by jour", cible)
    phrases = resume(kpi, alertes, prevision)
    print("\n".join(phrases))
    contenu = page(phrases, alertes)
    sortie = config.DATA_DIR / f"alerte_{date.today()}.html"
    sortie.write_text(contenu, encoding="utf-8")
    print("Page écrite :", sortie.name)
    envoyer(contenu)
