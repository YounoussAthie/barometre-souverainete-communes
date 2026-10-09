"""Construit le jeu de données final du baromètre à partir de la collecte brute.

Entrées :
  data/raw/all.psv               collecte DNS du 9 octobre 2026 (une ligne par commune)
  data/corrections_manuelles.csv vérifications manuelles documentées (source pour chaque ligne)
Sorties :
  data/communes_romandes_messagerie.csv
  data/synthese.json
"""
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATE_COLLECTE = "2026-10-09"

CATEGORIES = {
    "M": "Microsoft 365",
    "G": "Google Workspace",
    "S": "Prestataire suisse",
    "P": "Infrastructure publique",
    "F": "Passerelle de filtrage (plateforme non identifiée)",
    "C": "Serveur au nom de la commune",
    "A": "Autre",
    "N": "Non déterminé",
}
JURIDICTIONS = {
    "US": "Plateforme d'un fournisseur américain",
    "CH": "Prestataire ou infrastructure suisse",
    "CHUS": "Prestataire suisse avec filtrage par un fournisseur américain",
    "ND": "Non déterminé",
}
CANTONS = {"GE": "Genève", "VD": "Vaud", "NE": "Neuchâtel", "JU": "Jura", "FR": "Fribourg", "VS": "Valais"}


def lire_brut():
    lignes = []
    for brut in (ROOT / "data/raw/all.psv").read_text(encoding="utf-8").splitlines():
        bfs, nom, canton, domaine, lat, lon, mx, cat, fourn, juri, indice = brut.split("|")
        lignes.append(dict(bfs=int(bfs), commune=nom, canton=canton, domaine=domaine, lat=float(lat),
                           lon=float(lon), mx=mx, categorie=cat, fournisseur=fourn, juridiction=juri,
                           indice_spf=indice, correction="", source_correction=""))
    return lignes


# Fusions et changement de canton au 1er janvier 2026 (OFS, répertoire officiel des communes) :
# la population 2025 est publiée sous les anciens numéros.
FUSIONS_2026 = {2056: [2016, 2027],   # Fétigny + Ménières -> Fétigny-Ménières
                2262: [2262, 2278],   # Gurmels + Ulmiz -> Gurmels
                6831: [700]}          # Moutier passe du canton de Berne (700) au Jura (6831)


def lire_population():
    pop = {}
    for paire in (ROOT / "data/raw/population_2025.txt").read_text().strip().split(","):
        k, v = paire.split(":")
        pop[int(k)] = int(v)
    return pop


def appliquer_corrections(lignes):
    par_bfs = {l["bfs"]: l for l in lignes}
    with open(ROOT / "data/corrections_manuelles.csv", encoding="utf-8") as f:
        for c in csv.DictReader(f):
            l = par_bfs[int(c["bfs"])]
            l.update(domaine=c["domaine_messagerie"], mx=c["mx"], categorie=c["categorie"],
                     fournisseur=c["fournisseur"], juridiction=c["juridiction"],
                     correction=c["justification"], source_correction=c["source"])
    for l in lignes:
        # CIGES SA est une société anonyme informatique de Sion, pas une administration :
        # elle est classée comme prestataire suisse (filtrage entrant par Proofpoint).
        if l["fournisseur"].startswith("CIGES"):
            l["categorie"], l["fournisseur"] = "S", "CIGES SA, Sion (filtrage Proofpoint)"
        # rcv.ch est aussi l'infrastructure de messagerie de l'État de Vaud (MX de vd.ch).
        if l["fournisseur"].startswith("RCV"):
            l["fournisseur"] = "rcv.ch (infrastructure de messagerie de l'État de Vaud)"
        if l["fournisseur"].startswith("ACG"):
            l["fournisseur"] = "SIACG (informatique intercommunale genevoise)"
        if l["fournisseur"] == "Canton de Neuchâtel":
            l["fournisseur"] = "Canton de Neuchâtel (infrastructure ne.ch)"
        if l["fournisseur"] == "Canton de Neuchâtel (adresses @ne.ch)":
            l["fournisseur"] = "Canton de Neuchâtel (infrastructure ne.ch)"
        if l["categorie"] == "M" and not l["fournisseur"]:
            l["fournisseur"] = "Microsoft"
        if l["categorie"] == "G" and not l["fournisseur"]:
            l["fournisseur"] = "Google"
        if l["categorie"] == "C":
            l["fournisseur"] = "MX sur le domaine de la commune"
        if l["mx"] == "o365":
            l["mx"] = "<domaine>.mail.protection.outlook.com"
        l["mx"] = l["mx"].replace(" o365", " <domaine>.mail.protection.outlook.com")
        if l["indice_spf"] == "spfM":
            l["indice_spf"] = "Le SPF autorise Microsoft 365"
        elif l["indice_spf"].startswith("spf:"):
            l["indice_spf"] = "Le SPF autorise " + l["indice_spf"][4:]
    return lignes


def synthese(lignes):
    total = len(lignes)
    out = {"date_collecte": DATE_COLLECTE, "communes": total,
           "par_categorie": {}, "par_juridiction": {}, "par_canton": {}, "fournisseurs_suisses": {},
           "us_ou_filtrage_us": 0}
    cat = Counter(l["categorie"] for l in lignes)
    jur = Counter(l["juridiction"] for l in lignes)
    out["par_categorie"] = {CATEGORIES[k]: v for k, v in cat.most_common()}
    out["par_juridiction"] = {JURIDICTIONS[k]: v for k, v in jur.most_common()}
    out["us_ou_filtrage_us"] = jur["US"] + jur["CHUS"]
    pc = defaultdict(Counter)
    for l in lignes:
        pc[l["canton"]][l["categorie"]] += 1
        pc[l["canton"]]["_j_" + l["juridiction"]] += 1
    for k, c in pc.items():
        n = sum(v for kk, v in c.items() if not kk.startswith("_j_"))
        out["par_canton"][CANTONS[k]] = {"communes": n, **{CATEGORIES[x]: c[x] for x in CATEGORIES if c[x]},
                                        "part_microsoft_365": round(100 * c["M"] / n, 1)}
    pop_tot = sum(l["population_2025"] for l in lignes)
    out["population_2025"] = pop_tot
    out["population_par_juridiction"] = {JURIDICTIONS[k]: sum(l["population_2025"] for l in lignes if l["juridiction"] == k)
                                         for k in JURIDICTIONS}
    out["population_par_categorie"] = {CATEGORIES[k]: sum(l["population_2025"] for l in lignes if l["categorie"] == k)
                                       for k in CATEGORIES}
    for k, c in pc.items():
        n = [l for l in lignes if l["canton"] == k]
        p = sum(l["population_2025"] for l in n)
        out["par_canton"][CANTONS[k]]["population_2025"] = p
        out["par_canton"][CANTONS[k]]["part_population_fournisseur_us"] = round(
            100 * sum(l["population_2025"] for l in n if l["juridiction"] == "US") / p, 1)
    taille = {"< 1 000 hab.": (0, 1000), "1 000 – 4 999": (1000, 5000), "5 000 – 19 999": (5000, 20000),
              "≥ 20 000": (20000, 10**9)}
    out["par_taille"] = {}
    for lab, (a, b) in taille.items():
        g = [l for l in lignes if a <= l["population_2025"] < b]
        out["par_taille"][lab] = {"communes": len(g), **{CATEGORIES[x]: sum(1 for l in g if l["categorie"] == x)
                                                        for x in CATEGORIES},
                                 "part_microsoft_365": round(100 * sum(1 for l in g if l["categorie"] == "M") / len(g), 1)}
    sw = Counter(l["fournisseur"] for l in lignes if l["categorie"] in ("S", "P"))
    out["fournisseurs_suisses"] = dict(sw.most_common())
    out["spf_microsoft_hors_m365"] = sum(1 for l in lignes if l["categorie"] != "M" and "Microsoft" in l["indice_spf"])
    return out


def main():
    lignes = appliquer_corrections(lire_brut())
    lignes.sort(key=lambda l: l["bfs"])
    pop = lire_population()
    for l in lignes:
        l["population_2025"] = sum(pop[c] for c in FUSIONS_2026.get(l["bfs"], [l["bfs"]]))
    champs = ["bfs", "commune", "canton", "population_2025", "domaine", "mx", "categorie", "libelle_categorie", "fournisseur",
              "juridiction", "libelle_juridiction", "indice_spf", "lat", "lon", "correction", "source_correction"]
    with open(ROOT / "data/communes_romandes_messagerie.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=champs)
        w.writeheader()
        for l in lignes:
            w.writerow({**l, "libelle_categorie": CATEGORIES[l["categorie"]],
                        "libelle_juridiction": JURIDICTIONS[l["juridiction"]]})
    s = synthese(lignes)
    (ROOT / "data/synthese.json").write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
