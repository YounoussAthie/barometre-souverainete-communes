# Baromètre de la souveraineté numérique des communes romandes

Où sont hébergées les boîtes mail des 661 administrations communales de Suisse romande ? Ce projet mesure, à partir des seuls enregistrements DNS publics, quelle part des communes de Genève, Vaud, Neuchâtel, Jura, Fribourg et Valais confie sa messagerie à un fournisseur soumis au CLOUD Act américain, et quelle part passe par un prestataire ou une infrastructure suisse.

État des données : 9 octobre 2026.

## Résultats principaux

| | Communes | Population (31.12.2025) |
|---|---|---|
| Microsoft 365 ou Google Workspace | 356 (53,9 %) | 1 037 241 (43,4 %) |
| Prestataire ou infrastructure suisse | 241 (36,5 %) | 939 376 (39,3 %) |
| Prestataire suisse avec filtrage par un fournisseur américain | 17 (2,6 %) | 114 495 (4,8 %) |
| Non déterminé (serveur propre, passerelle opaque, pas de domaine) | 47 (7,1 %) | 299 249 (12,5 %) |

- Les écarts entre cantons sont nets : 70,6 % des communes fribourgeoises sont sur Microsoft 365, contre 2,2 % à Genève et 0 % à Neuchâtel, où la messagerie est mutualisée (SIACG à Genève, infrastructure cantonale ne.ch à Neuchâtel).
- Ce sont les communes de 1 000 à 5 000 habitants qui passent le plus par Microsoft 365 (63,8 %). Les villes de plus de 20 000 habitants y recourent beaucoup moins (23,5 %), sauf exceptions comme la Ville de Genève.
- Infomaniak est le premier prestataire suisse (94 communes).
- 21 communes qui ne sont pas sur Microsoft 365 autorisent quand même ses serveurs dans leur enregistrement SPF, signe d'un usage partiel ou d'une migration en cours.

## Méthode

1. Liste officielle des communes au 9.10.2026 (OFS, API du répertoire officiel des communes).
2. Domaine de chaque commune : site officiel déclaré dans Wikidata (P856), rattaché par le numéro OFS.
3. Requêtes DNS publiques (MX, TXT/SPF, NS) par DNS-over-HTTPS.
4. Classement selon le serveur qui reçoit le courrier (MX). Quand le MX est une passerelle de filtrage (Proofpoint, Hornetsecurity, Sophos, etc.), le SPF sert à identifier la plateforme qui se trouve derrière.
5. Vérifications manuelles pour les 23 communes dont le domaine n'avait pas de MX exploitable : adresses de contact relevées sur leurs sites (voir `data/corrections_manuelles.csv`, une source par ligne). 22 ont pu être rattachées à leur vrai domaine de messagerie ; restent 5 communes non déterminées (Villorsonnens et 4 communes sans site officiel référencé).
6. Contrôle : 18 domaines tirés au sort ou importants interrogés une seconde fois via un autre résolveur (Cloudflare), sans écart.

## Limites

- Le MX montre où le courrier est reçu, pas où sont stockés les autres documents (Teams, OneDrive, logiciels métier, sauvegardes). Une commune peut recevoir ses mails en Suisse et stocker ses fichiers chez Microsoft, ou l'inverse.
- « Serveur au nom de la commune » ne dit pas qui exploite la machine. L'indice SPF donne parfois une piste (hébergeur suisse ou Microsoft), mais ce n'est pas une preuve.
- Les filiales européennes des fournisseurs américains restent soumises au CLOUD Act ; la localisation des centres de données ne change pas ce classement.
- Les domaines viennent de Wikidata, qui peut être en retard sur les fusions ou les changements de site. Les cas sans MX ont été vérifiés à la main, pas les autres.
- Les données décrivent une configuration publique à une date donnée. Elles ne disent rien de la sécurité ni de la conformité de chaque commune.

## Contenu du dépôt

```
data/
  communes_romandes_messagerie.csv   table finale, une ligne par commune
  synthese.json                      chiffres agrégés
  metadonnees.jsonld                 description du jeu de données (DCAT-AP)
  corrections_manuelles.csv          vérifications manuelles et leurs sources
  raw/                               collecte brute et population OFS
scripts/
  collecte.py                        liste OFS + Wikidata + DNS -> data/raw/all.psv
  construire_jeu_de_donnees.py       corrections + population -> CSV et synthèse
  generer_page.py                    CSV + synthèse -> site/barometre.html
site/
  template.html, barometre.html      page interactive (carte, cantons, registre)
```

Pour refaire la mesure :

```
pip install requests
python scripts/collecte.py --date 09-10-2027
python scripts/construire_jeu_de_donnees.py
python scripts/generer_page.py
```

## Cadre

- Résolution de privatim (conférence des préposé·e·s suisses à la protection des données) du 18 novembre 2025 sur l'externalisation de traitements de données dans le cloud.
- Stratégie Suisse numérique 2026, dont la souveraineté numérique est l'un des trois thèmes prioritaires.
- Loi fédérale sur la protection des données (nLPD) et lois cantonales sur l'information et la protection des données.

## Licence

Données et code sous CC BY 4.0. Sources : OFS (répertoire officiel des communes, STATPOP), Wikidata (CC0).
