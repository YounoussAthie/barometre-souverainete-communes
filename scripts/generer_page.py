"""Génère site/barometre.html (page interactive) à partir du CSV final et de la synthèse."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

lignes = []
with open(ROOT / "data/communes_romandes_messagerie.csv", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        fournisseur = r["fournisseur"]
        if r["categorie"] == "C" and r["indice_spf"]:
            fournisseur += " · " + r["indice_spf"]
        lignes.append({"n": r["commune"], "c": r["canton"], "p": int(r["population_2025"]), "d": r["domaine"],
                       "m": r["mx"].replace("<domaine>", "…"), "f": fournisseur, "j": r["juridiction"],
                       "lat": float(r["lat"]), "lon": float(r["lon"])})
synthese = json.loads((ROOT / "data/synthese.json").read_text(encoding="utf-8"))
page = (ROOT / "site/template.html").read_text(encoding="utf-8")
page = page.replace("__DATA__", json.dumps(lignes, ensure_ascii=False, separators=(",", ":")))
page = page.replace("__SYNTH__", json.dumps(synthese, ensure_ascii=False, separators=(",", ":")))
(ROOT / "site/barometre.html").write_text(page, encoding="utf-8")
print(f"site/barometre.html : {len(lignes)} communes")
