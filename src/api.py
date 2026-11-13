"""Lire une API en JSON, avec des relances si le réseau ou l'API hésitent."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request


def lire_json(url, params=None, essais=4, pause=1.0):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    for essai in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "sante-tiers/1.0"})
            with urllib.request.urlopen(req, timeout=30) as reponse:
                return json.loads(reponse.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:        # trop de demandes, ou l'API est en difficulté
                time.sleep(pause * (essai + 1) * 2)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(pause * (essai + 1))
    raise RuntimeError(f"API injoignable après {essais} essais : {url[:90]}")
