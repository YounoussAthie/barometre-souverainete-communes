"""Collecte des données du baromètre : communes romandes -> domaine -> enregistrements DNS.

Étapes
  1. Liste officielle des communes (OFS, répertoire officiel des communes, API AGVCH) à la date choisie.
  2. Site officiel de chaque commune (Wikidata, propriété P856), rattaché par le numéro OFS (P771).
  3. Requêtes DNS publiques (MX, TXT/SPF, NS) via DNS-over-HTTPS (Google Public DNS).
  4. Classement du fournisseur de messagerie (règles dans classer()).

Sortie : data/raw/all.psv (format lu par construire_jeu_de_donnees.py)

Usage : python scripts/collecte.py --date 09-10-2026
Dépendance : requests
"""
import argparse
import concurrent.futures as cf
import csv
import io
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "barometre-souverainete-communes/1.0 (projet academique)"}

# Plages de numéros OFS des cantons couverts
PLAGES = {"FR": (2001, 2399), "VD": (5401, 5999), "VS": (6001, 6399), "NE": (6401, 6599),
          "GE": (6601, 6699), "JU": (6701, 6899)}

PUBLIC = {"acg-geneve.ch": "ACG (Association des communes genevoises)", "rcv.ch": "RCV (réseau cantonal vaudois)",
          "ne.ch": "Canton de Neuchâtel"}
SUISSES = {"infomaniak.ch": "Infomaniak", "evok.ch": "Evok", "azinformatique.ch": "AZ Informatique",
           "ti-informatique.com": "T.I. Informatique", "witecom.ch": "Witecom", "telecomservices.ch": "Telecomservices",
           "rhone.ch": "Rhône.ch", "rufcloud.ch": "Ruf Cloud", "swisscenter.com": "Swisscenter", "pcprofi.ch": "PC Profi",
           "senselan.ch": "Senselan", "horus.ch": "Horus", "netplus.ch": "Netplus", "vtx.ch": "VTX",
           "safecenter.ch": "Safecenter", "cleanmail.ch": "Cleanmail", "swizzonic.email": "Swizzonic", "dlnet.ch": "DLNet",
           "hostpoint.ch": "Hostpoint", "vs-online.net": "VS-Online", "jse.ch": "JSE",
           "hornetsecurity.ch": "Hornetsecurity (filtrage)"}
PASSERELLES = {"ppe-hosted.com": "Proofpoint", "spamvor.com": "Spamvor", "sophos.com": "Sophos",
               "hornetsecurity.com": "Hornetsecurity", "spamexperts.com": "SpamExperts", "spamexperts.eu": "SpamExperts",
               "spamexperts.net": "SpamExperts", "fortimailcloud.com": "FortiMail Cloud", "spamtitan.com": "SpamTitan",
               "mtaroutes.com": "MTA Routes", "iphmx.com": "Cisco Secure Email",
               "barracudanetworks.com": "Barracuda", "seppmail.cloud": "SEPPmail", "antispamcloud.com": "Antispamcloud"}
PASSERELLES_US = {"Proofpoint", "Cisco Secure Email", "Barracuda", "FortiMail Cloud"}
AUTRES = {"registrar-servers.com": "Namecheap", "pinhaotec.com": "Pinhaotec"}
SPF_SUISSES = {"kreativmedia.ch": "Kreativmedia", "sui-inter.net": "Sui-Inter", "tizoo.com": "Tizoo",
               "infomaniak.ch": "Infomaniak", "ganesh-hosting.ch": "Ganesh Hosting", "swizzonic-mail.ch": "Swizzonic",
               "cyon.net": "Cyon"}


def communes(date):
    url = f"https://www.agvchapp.bfs.admin.ch/api/communes/snapshot?date={date}"
    rows = list(csv.reader(io.StringIO(requests.get(url, headers=UA, timeout=60).text)))[1:]
    out = []
    for r in rows:
        if r[4] != "3" or r[3]:
            continue
        bfs = int(r[1])
        canton = next((c for c, (a, b) in PLAGES.items() if a <= bfs <= b), None)
        if canton:
            out.append({"bfs": bfs, "nom": r[6], "canton": canton})
    return out


def sites_wikidata():
    q = """SELECT ?bfs ?web ?lat ?lon WHERE { ?c wdt:P31 wd:Q70208 ; wdt:P771 ?bfs .
      OPTIONAL { ?c wdt:P856 ?web }
      OPTIONAL { ?c p:P625/psv:P625 [ wikibase:geoLatitude ?lat ; wikibase:geoLongitude ?lon ] } }"""
    j = requests.get("https://query.wikidata.org/sparql", params={"query": q, "format": "json"},
                     headers=UA, timeout=120).json()
    out = {}
    for b in j["results"]["bindings"]:
        k = int(b["bfs"]["value"])
        d = out.setdefault(k, {"webs": set(), "lat": None, "lon": None})
        if "web" in b:
            host = urlparse(b["web"]["value"]).hostname or ""
            d["webs"].add(host.removeprefix("www.").lower())
        if "lat" in b and d["lat"] is None:
            d["lat"], d["lon"] = float(b["lat"]["value"]), float(b["lon"]["value"])
    return out


def doh(name, rtype):
    code = {"MX": 15, "TXT": 16, "NS": 2}[rtype]
    for essai in range(3):
        try:
            j = requests.get("https://dns.google/resolve", params={"name": name, "type": rtype},
                             headers=UA, timeout=20).json()
            return j.get("Status", -1), [a["data"] for a in j.get("Answer", []) if a["type"] == code]
        except requests.RequestException:
            time.sleep(1 + essai)
    return -1, []


def enregistrements(domaine):
    _, mx = doh(domaine, "MX")
    _, txt = doh(domaine, "TXT")
    if not mx:  # sous-domaine (gemeinde.xyz.ch) : on remonte au domaine enregistrable
        parent = ".".join(domaine.split(".")[-2:])
        if parent != domaine:
            _, mx2 = doh(parent, "MX")
            if mx2:
                domaine, mx = parent, mx2
                _, txt = doh(parent, "TXT")
    mx = [m.split()[-1].rstrip(".").lower() for m in mx]
    spf = " ".join(t.replace('"', "") for t in txt if "v=spf1" in t.lower())
    return domaine, mx, spf


def enregistrable(h):
    return ".".join(h.split(".")[-2:])


def classer(domaine, mx, spf):
    regs = list(dict.fromkeys(enregistrable(h) for h in mx))
    inclus = " ".join(t.split(":", 1)[-1].split("=", 1)[-1] for t in spf.lower().split()
                      if t.startswith(("include:", "redirect=")))
    spf_m365 = "protection.outlook.com" in inclus
    spf_google = "_spf.google.com" in inclus
    if not mx:
        return "N", "Aucun enregistrement MX sur le domaine", "ND", ""
    if {"outlook.com", "onmicrosoft.com"} & set(regs):
        return "M", "", "US", ""
    if {"google.com", "googlemail.com"} & set(regs):
        return "G", "", "US", ""
    for r in regs:
        if r in PUBLIC:
            return "P", PUBLIC[r], "CH", "spfM" if spf_m365 else ""
    for r in regs:
        if r in PASSERELLES or r == "hornetsecurity.ch":
            nom = PASSERELLES.get(r) or SUISSES[r]
            if spf_m365:
                return "M", f"Microsoft (derrière filtrage {nom})", "US", ""
            if spf_google:
                return "G", f"Google (derrière filtrage {nom})", "US", ""
            if "clients.ciges.ch" in inclus and nom == "Proofpoint":
                return "P", "CIGES (filtrage Proofpoint)", "CHUS", ""
            return "F", nom, "CHUS" if nom in PASSERELLES_US else "ND", ""
    for r in regs:
        if r in SUISSES:
            return "S", SUISSES[r], "CH", "spfM" if spf_m365 else ""
    for r in regs:
        if r in AUTRES:
            return "A", AUTRES[r], "ND", ""
    indice = "spfM" if spf_m365 else next((f"spf:{v}" for k, v in SPF_SUISSES.items() if k in inclus), "")
    return "C", "", "ND", indice


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=time.strftime("%d-%m-%Y"))
    args = ap.parse_args()
    liste = communes(args.date)
    wd = sites_wikidata()

    def traiter(c):
        info = wd.get(c["bfs"], {"webs": set(), "lat": None, "lon": None})
        webs = sorted(info["webs"])
        domaine = next((w for w in webs if w.endswith(".ch")), webs[0] if webs else "")
        if not domaine:
            return [c["bfs"], c["nom"], c["canton"], "", info["lat"], info["lon"], "", "N",
                    "Pas de site officiel référencé", "ND", ""]
        dom, mx, spf = enregistrements(domaine)
        cat, fourn, jur, indice = classer(dom, mx, spf)
        mx_court = " ".join(dict.fromkeys("o365" if h.endswith(".mail.protection.outlook.com") else h for h in mx[:2]))
        return [c["bfs"], c["nom"], c["canton"], dom, f"{info['lat']:.3f}", f"{info['lon']:.3f}", mx_court, cat,
                fourn, jur, indice]

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        lignes = sorted(ex.map(traiter, liste), key=lambda l: l[0])
    sortie = ROOT / "data/raw/all.psv"
    sortie.write_text("\n".join("|".join(str(x) for x in l) for l in lignes) + "\n", encoding="utf-8")
    print(f"{len(lignes)} communes écrites dans {sortie}")


if __name__ == "__main__":
    main()
