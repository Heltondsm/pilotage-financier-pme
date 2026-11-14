"""Le serveur de l'assistant du DAF : il sert la page HTML (dossier interface/) et répond à ses questions.

Lancer depuis la racine du projet (après « source activer.sh ») :
    python serveur_assistant.py
Puis ouvrir http://localhost:8501 (c'est ce lien que vise le bouton du rapport Power BI).
"""
import functools
import math
import os
import time
import urllib.error
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from assistant import REPONSE_REFUS, repondre

CIBLE = os.environ.get("ASSISTANT_CIBLE", "local")      # « bigquery » pour lire directement l'entrepôt GCP
DOSSIER = Path(__file__).parent / "interface"

app = FastAPI(title="Assistant du DAF")


class Question(BaseModel):
    question: str


def valeur(v):
    """Une case du tableau, prête pour le JSON (dates en AAAA-MM-JJ, nombres tels quels, vides à null)."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp) or hasattr(v, "isoformat"):
        return v.isoformat()[:10]
    if hasattr(v, "item"):                               # entiers et décimaux numpy
        return v.item()
    return v


@functools.lru_cache(maxsize=200)                         # une question déjà posée répond tout de suite
def interroger(question):
    debut = time.time()
    sql, tableau, phrase = repondre(question, CIBLE)
    reponse = {"phrase": phrase, "sql": sql.replace("{schema}.", "") if sql else None,
               "statut": "refus" if phrase == REPONSE_REFUS else ("ok" if sql else "echec"),
               "duree": round(time.time() - debut, 1), "colonnes": [], "types": [], "lignes": []}
    if tableau is not None:
        tableau = tableau.head(50)
        reponse["colonnes"] = list(tableau.columns)
        reponse["types"] = ["date" if pd.api.types.is_datetime64_any_dtype(t) or c in ("mois", "jour")
                            else "nombre" if pd.api.types.is_numeric_dtype(t) and not pd.api.types.is_bool_dtype(t)
                            else "texte" for c, t in tableau.dtypes.items()]
        reponse["lignes"] = [[valeur(v) for v in ligne] for ligne in tableau.itertuples(index=False)]
    return reponse


@app.post("/api/question")
def question(q: Question):
    texte = " ".join(q.question.split())[:300]
    if not texte:
        return {"statut": "echec", "phrase": "Posez une question sur les ventes, les clients, la trésorerie ou le secteur."}
    try:
        return interroger(texte)
    except urllib.error.HTTPError as erreur:
        message = ("Trop de questions en une minute pour la version gratuite de Gemini : réessayez dans un instant."
                   if erreur.code == 429 else f"Gemini ne répond pas pour l'instant (erreur {erreur.code}).")
        return {"statut": "echec", "phrase": message}
    except SystemExit as erreur:                         # clé Gemini absente
        return {"statut": "echec", "phrase": str(erreur)}


@app.get("/")
def page():
    return FileResponse(DOSSIER / "index.html")


app.mount("/", StaticFiles(directory=DOSSIER), name="interface")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8501)
