"""Le diagnostic d'une page d'une entreprise (données réelles), à joindre à une candidature.

    python diagnostic.py 410288476                 -> data/diagnostics/<siren>.html (+ .pdf si Chrome est là)
    python diagnostic.py --liste cibles.csv        -> un diagnostic par SIREN de la colonne « siren »
"""
import argparse
import csv
import html
import shutil
import subprocess

from src import config
from src.entrepot import lire

DOSSIER = config.DATA_DIR / "diagnostics"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
INDICATEURS = [  # colonne, libellé, unité, « plus haut = mieux ? »
    ("croissance_pct", "Croissance des ventes", "%", True),
    ("marge_ebe_pct", "Marge (EBE / ventes)", "%", True),
    ("delai_clients_jours", "Délai de paiement des clients", "jours", False),
    ("delai_fournisseurs_jours", "Délai de paiement des fournisseurs", "jours", None),
    ("endettement_pct", "Endettement", "%", False),
]


def ligne_indicateur(b, col, libelle, unite, plus_haut_mieux):
    v, m = b[col], b[f"{col}_mediane"]
    if v != v or m != m:                                  # valeur absente (comptes confidentiels…)
        return f"<tr><td>{libelle}</td><td colspan='3' style='color:#888'>non publié</td></tr>"
    if plus_haut_mieux is None:
        lecture = "plus lent que le secteur" if v > m else "plus rapide que le secteur"
    else:
        mieux = v >= m if plus_haut_mieux else v <= m
        lecture = "✅ meilleur que le secteur" if mieux else "⚠️ moins bon que le secteur"
    fmt = (lambda x: f"{x:.1f}".replace(".", ",")) if unite == "%" else (lambda x: f"{x:.0f}")
    return f"<tr><td>{libelle}</td><td><b>{fmt(v)} {unite}</b></td><td>{fmt(m)} {unite}</td><td>{lecture}</td></tr>"


def fabriquer(siren, cible="local"):
    if not (isinstance(siren, str) and siren.isdigit() and len(siren) == 9):
        print(f"{siren!r} : il faut un SIREN à 9 chiffres")      # protège aussi la requête SQL
        return None
    b = lire(f"select * from {{schema}}.benchmark_entreprises where siren = '{siren}'", cible)
    d = lire(f"select * from {{schema}}.diagnostic_entreprises where siren = '{siren}'", cible)
    if b.empty or d.empty:
        print(f"{siren} : pas de bilan complet récent, ou trop peu de concurrents comparables")
        return None
    b, d = b.iloc[0], d.iloc[0]
    tableau = "".join(ligne_indicateur(b, *i) for i in INDICATEURS)
    constats = "".join(f"<li>{html.escape(d[c])}</li>" for c in ["constat_croissance", "constat_marge", "constat_clients",
                                                                 "constat_fournisseurs"] if d[c])
    recos = "".join(f"<li>{html.escape(d[r])}</li>" for r in ["recommandation_1", "recommandation_2"] if d[r])
    contenu = f"""<!doctype html><html lang="fr"><meta charset="utf-8"><style>
body{{font-family:Arial,sans-serif;color:#1d2433;max-width:760px;margin:30px auto}}h1{{color:#08306B;font-size:22px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #dde3ec;padding:7px;text-align:left}}
.reco{{background:#eef3fb;border-left:4px solid #376dae;padding:6px 16px}}small{{color:#737373}}</style>
<h1>{html.escape(str(b["nom"]))} face à son secteur</h1>
<p>Exercice {int(b["exercice"])} · comparée aux {int(b["nb_concurrents"])} entreprises de même activité et de même taille
(groupe {html.escape(b["groupe"])}).</p>
<table><tr><th>Indicateur</th><th>L'entreprise</th><th>Médiane du secteur</th><th>Lecture</th></tr>{tableau}</table>
<h3>Ce que montrent les comptes</h3><ul>{constats}</ul>
<div class="reco"><h3>Ce que je recommande</h3><ul>{recos}</ul></div>
<p><small>Source : comptes annuels publics (INPI / BCE) et annuaire Sirene. Diagnostic automatique, à confirmer avec
les données internes de l'entreprise.</small></p></html>"""
    DOSSIER.mkdir(exist_ok=True)
    sortie = DOSSIER / f"{siren}.html"
    sortie.write_text(contenu, encoding="utf-8")
    if shutil.which(CHROME) or __import__("os").path.exists(CHROME):
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={sortie.with_suffix('.pdf')}", sortie.as_uri()], capture_output=True)
    print(f"{siren} : {sortie.name}")
    return sortie


if __name__ == "__main__":
    options = argparse.ArgumentParser()
    options.add_argument("siren", nargs="?")
    options.add_argument("--liste")
    options.add_argument("--cible", choices=["local", "bigquery"], default="local")
    o = options.parse_args()
    sirens = [o.siren] if o.siren else [l["siren"] for l in csv.DictReader(open(o.liste, encoding="utf-8")) if l.get("siren")]
    for s in sirens:
        fabriquer(s, o.cible)
