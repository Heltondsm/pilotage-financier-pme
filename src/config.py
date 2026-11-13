"""Les réglages du projet : chemins, adresses des sources, et l'entreprise de démonstration."""
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # le dossier du projet
DATA_DIR = ROOT / "data"                           # tout ce qui est téléchargé ou simulé
REF_DIR = DATA_DIR / "referentiels"                # les gros fichiers publics (bilans, annuaire)
SIMU_DIR = DATA_DIR / "distrimat"                  # les données de test de Distrimat
SEEDS_DIR = ROOT / "dbt" / "seeds"
for dossier in (DATA_DIR, REF_DIR, SIMU_DIR):
    dossier.mkdir(parents=True, exist_ok=True)

# --- les sources publiques (gratuites, sans clé)
URL_ENTREPRISES = "https://recherche-entreprises.api.gouv.fr/search"
URL_BODACC = "https://bodacc-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/annonces-commerciales/records"
URL_BILANS_PARQUET = "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/ratios_inpi_bce/exports/parquet"
URL_JEU_SIRENE = "https://www.data.gouv.fr/api/1/datasets/5b7ffc618b4c4169d30727e0/"   # base Sirene (on y cherche le dernier fichier)

# --- Distrimat, l'entreprise FICTIVE de démonstration
NAF_DISTRIMAT = "46.73A"          # commerce de gros de bois et de matériaux de construction
TRANCHES_PAIRS = ["21"]           # 50 à 99 salariés : ses concurrents de même taille
DEBUT_SIMULATION = date(2024, 1, 1)
GRAINE = 42                       # le hasard est fixé : mêmes données à chaque fois

# ses clients : de vraies entreprises du bâtiment d'Île-de-France (affichées sous un code, jamais par leur nom)
DEPARTEMENTS_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]
NAF_CLIENTS = ["41.20A", "41.20B", "43.21A", "43.22A", "43.22B", "43.31Z", "43.32A", "43.33Z",
               "43.34Z", "43.39Z", "43.91B", "43.99C"]
NB_CLIENTS = 800
# ses fournisseurs : de vrais fabricants de matériaux
NAF_FOURNISSEURS = ["23.61Z", "23.32Z", "23.62Z", "23.51Z", "16.23Z", "23.99Z", "25.11Z", "22.23Z"]
NB_FOURNISSEURS = 60
