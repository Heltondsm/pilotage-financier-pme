"""La prévision de trésorerie vaut-elle quelque chose ? On la refait à 5 dates passées, avec seulement
ce qu'on savait ce jour-là, et on la compare au solde réellement constaté 30, 60 et 90 jours plus tard.

    python backtest.py          (local seulement ; 2 à 3 minutes)
Résultat : data/backtest_tresorerie.csv, et un résumé à l'écran.
"""
import subprocess

import duckdb
import pandas as pd

from src import config

DATES = ["2025-07-31", "2025-10-31", "2026-01-31", "2026-04-30", "2026-07-31"]
DBT = config.ROOT / ".venv" / "bin" / "dbt"


def dbt(*arguments):
    subprocess.run([str(DBT), *arguments, "--profiles-dir", ".", "--target", "backtest", "--quiet"],
                   cwd=config.ROOT / "dbt", check=True)


def main():
    dbt("seed")                                                   # les fichiers de référence, dans le schéma à part
    lignes = []
    for date_ref in DATES:
        dbt("run", "--select", "+prevision_tresorerie", "--vars", f"{{date_reference: {date_ref}}}")
        base = duckdb.connect(str(config.ROOT / "entrepot.duckdb"), read_only=True)
        comparaison = base.execute("""
            select p.jour, p.solde_prevu, r.solde as solde_reel
            from pilotage_backtest.prevision_tresorerie p
            join pilotage.tresorerie_jour r on r.jour = p.jour
        """).df()
        depart = base.execute("select solde from pilotage_backtest.tresorerie_jour order by jour desc limit 1").fetchone()[0]
        base.close()
        for horizon in (30, 60, 90):
            jour = pd.Timestamp(date_ref) + pd.Timedelta(days=horizon)
            proche = comparaison.iloc[(pd.to_datetime(comparaison["jour"]) - jour).abs().argsort()[:1]].iloc[0]
            lignes.append({"date_prevision": date_ref, "horizon_jours": horizon, "jour": proche["jour"],
                           "solde_depart": round(depart), "solde_prevu": round(proche["solde_prevu"]),
                           "solde_reel": round(proche["solde_reel"]),
                           "ecart_pct": round(100 * (proche["solde_prevu"] / proche["solde_reel"] - 1), 1)})
    resultat = pd.DataFrame(lignes)
    resultat.to_csv(config.DATA_DIR / "backtest_tresorerie.csv", index=False)
    print(resultat.to_string(index=False))
    print("\nÉcart moyen (en valeur absolue) :")
    print(resultat.assign(ecart_abs=resultat["ecart_pct"].abs()).groupby("horizon_jours")["ecart_abs"].mean().round(1).to_string())


if __name__ == "__main__":
    main()
