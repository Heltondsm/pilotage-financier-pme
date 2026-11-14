"""L'assistant du DAF : une question en français -> une requête SQL -> une réponse en français.

Il utilise Gemini (Google), gratuit dans la limite d'un certain nombre de questions par jour.
Garde-fous : il ne peut que LIRE, et seulement les tables de pilotage de Distrimat.

    export GEMINI_API_KEY="ta-clé"          (créée sur aistudio.google.com, sans carte bancaire)
    python assistant.py "Quels clients nous doivent le plus d'argent ?"
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from src.entrepot import lire

MODELE = os.environ.get("GEMINI_MODELE", "gemini-flash-lite-latest")   # rapide et gratuit
TABLES_AUTORISEES = ["kpi_mensuels", "ventes_familles", "balance_agee", "tresorerie_jour", "prevision_tresorerie",
                     "alertes_clients", "position_distrimat"]
# Le dictionnaire métier : sans lui, l'IA invente ses propres définitions (testé : à la question « quelle
# famille est la plus en retard sur son budget sur 12 mois ? », elle comparait des euros sur 3 ans)
DICTIONNAIRE = """Règles à respecter :
- Les montants de ventes, de marge et de budget sont HORS TAXES (ca_ht, budget_ht, marge_brute_ht) ;
  ce que doivent les clients et la banque sont TOUTES TAXES COMPRISES (…_ttc, solde).
- La date d'aujourd'hui pour les calculs est la DERNIÈRE date des données (max(mois) ou max(jour)),
  jamais la date du système. « Les 12 derniers mois » = les 12 mois jusqu'à max(mois) compris.
- Écart au budget = (somme des ventes - somme du budget) / somme du budget, en pourcentage, seulement
  sur les lignes où budget_ht n'est pas vide (le budget commence en 2025).
- Taux de marge = somme de marge_brute_ht / somme de ca_ht.
- DSO = délai de paiement des clients en jours (kpi_mensuels.dso_jours) ; la moyenne des 12 derniers mois
  est celle qu'on compare au secteur.
- Un client « en retard de plus de 60 jours » : retard_61_90 + retard_plus_90 (balance_agee).
- La comparaison au secteur est dans position_distrimat : une ligne par indicateur (ordre 1 = croissance des
  ventes, 2 = marge EBE / ventes, 3 = délai de paiement des clients, 4 = délai de paiement des fournisseurs) ;
  la colonne distrimat = l'entreprise, q1 / mediane / q3 = le secteur (nb_entreprises comparées).
- Renvoie TOUJOURS, en plus des libellés, les chiffres qui justifient la réponse (montants, pourcentages).
- Si la question demande de modifier, supprimer ou créer quoi que ce soit, ou une information absente des
  tables (les SIREN, les noms des clients), réponds seulement par le mot : REFUS"""

REPONSE_REFUS = ("Je ne peux que lire les tables de pilotage, sans rien modifier, et les clients n'y apparaissent "
                 "que sous un code (C0001…) : leur nom et leur SIREN ne sont pas accessibles.")

INTERDITS = r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|install|load|export|call|grant|merge)\b"


def demander_a_gemini(texte):
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle:
        raise SystemExit("Il manque la clé GEMINI_API_KEY (voir le guide, étape de l'assistant).")
    corps = json.dumps({"contents": [{"parts": [{"text": texte}]}],
                        "generationConfig": {"temperature": 0}}).encode()
    requete = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODELE}:generateContent",
        data=corps, headers={"Content-Type": "application/json", "x-goog-api-key": cle})
    for essai in range(4):
        try:
            with urllib.request.urlopen(requete, timeout=120) as reponse:
                resultat = json.loads(reponse.read())
            break
        except urllib.error.HTTPError as erreur:
            if erreur.code != 429 or essai == 3:        # 429 = trop de questions en une minute (forfait gratuit)
                raise
            time.sleep(20 * (essai + 1))                # on attend un peu, puis on réessaie
    parties = resultat["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parties if not p.get("thought")).strip()


def description_des_tables(cible):
    """La liste des tables autorisées et de leurs colonnes, à donner à Gemini."""
    lignes = []
    for table in TABLES_AUTORISEES:
        colonnes = lire(f"select * from {{schema}}.{table} limit 0", cible).columns
        lignes.append(f"- {{schema}}.{table}({', '.join(colonnes)})")
    return "\n".join(lignes)


def verifier(sql):
    """Refuse tout ce qui n'est pas UNE requête de lecture sur les tables autorisées."""
    sql = sql.strip().removeprefix("```sql").removeprefix("```").removesuffix("```").strip().rstrip(";")
    if ";" in sql:
        raise ValueError("une seule requête à la fois")
    if not re.match(r"(?is)^\s*(with|select)\b", sql) or re.search(INTERDITS, sql, re.I):
        raise ValueError("seules les requêtes de lecture sont permises")
    if re.search(r"(?i)\b(brut|information_schema|main|pg_catalog)\s*\.|\bread_\w+\s*\(|\bglob\s*\(|\bduckdb_\w+", sql):
        raise ValueError("seules les tables de pilotage sont permises")
    tables = set(re.findall(r"\{schema\}\.(\w+)", sql))
    if not tables or not tables <= set(TABLES_AUTORISEES):
        raise ValueError(f"tables non autorisées : {tables - set(TABLES_AUTORISEES) or 'aucune table'}")
    return sql if re.search(r"(?i)\blimit\s+\d+\s*$", sql) else sql + " limit 200"


def repondre(question, cible="local"):
    consigne = (
        "Tu aides le directeur financier de Distrimat (données de test). Écris UNE requête SQL "
        f"({'BigQuery' if cible == 'bigquery' else 'DuckDB'}) de lecture qui répond à la question, en utilisant "
        "UNIQUEMENT ces tables, en gardant le préfixe {schema} tel quel :\n"
        f"{description_des_tables(cible)}\n{DICTIONNAIRE}\nRéponds seulement par la requête, sans explication.\n"
        f"Question : {question}")
    sql, tableau = None, None
    for essai in range(3):                       # si la requête échoue, Gemini reçoit l'erreur et corrige (2 fois au plus)
        try:
            texte = demander_a_gemini(consigne)
            if texte.strip().strip(".").upper() == "REFUS":
                return None, None, REPONSE_REFUS
            sql = verifier(texte)
            tableau = lire(sql, cible)
            break
        except urllib.error.HTTPError:           # un problème avec Gemini lui-même : on ne le maquille pas
            raise
        except Exception as erreur:              # requête refusée par les garde-fous, ou rejetée par l'entrepôt
            consigne += f"\nTa requête précédente a échoué : {str(erreur)[:300]}\nCorrige-la."
    if tableau is None:
        return sql, None, "Je n'ai pas réussi à écrire une requête correcte pour cette question. Reformule-la, plus simplement."
    phrase = demander_a_gemini(
        f"Question du directeur financier : {question}\nRésultat (tableau) :\n{tableau.head(20).to_string()}\n"
        "Réponds en 2 phrases simples en français, avec les chiffres du tableau. N'invente aucun chiffre. "
        "Si le tableau est vide, dis que tu n'as trouvé aucune donnée. Tu n'as rien modifié : ne prétends jamais "
        "avoir supprimé, créé ou changé quoi que ce soit.")
    return sql, tableau, phrase


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "Quels clients nous doivent le plus d'argent ?"
    sql, tableau, phrase = repondre(question)
    if sql:
        print("Requête :", sql, "\n")
    if tableau is not None:
        print(tableau.head(10).to_string(), "\n")
    print(phrase)
