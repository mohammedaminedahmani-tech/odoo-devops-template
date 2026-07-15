# -*- coding: utf-8 -*-
"""
regrouper_pistes.py — Detecte les fondations partagees (points de fork) et
regroupe le reste en branches paralleles independantes.

PROBLEME RESOLU : un simple union-find fusionne a tort deux pistes qui
partagent juste un ANCETRE COMMUN (ex: 3 pistes qui dependent toutes de
"config") meme si elles n'ont AUCUN lien entre elles. Ca fait collapser tout
un module en un seul groupe geant des qu'il y a des fondations partagees
(config, referentiel produit, etc.), ce qui annule tout le parallelisme.

NOUVEL ALGORITHME :
  1. Detecte les "forks" : une piste F est un fork si au moins 2 de ses
     descendants ne dependent PAS l'un de l'autre (= 2 branches vraiment
     independantes qui ont juste besoin des donnees de F).
  2. Les forks partent dans une phase "SETUP" (executee UNE FOIS, en
     sequence, avant tout le reste).
  3. Le reste des pistes (non-fork) est regroupe normalement (union-find)
     mais en ignorant les aretes qui pointent vers un fork (deja resolu
     par le setup) -> ca revele les vraies branches paralleles.

Lit : contrats/<module>_resume.md (section === PISTES === au format id|nom|depends_on)
Ecrit sur stdout un JSON :
  {
    "setup": {"pistes": ["config", "site_referentiel", "catalogue_produit", "inventaire_site"]},
    "groupes": [
      {"groupe": "grp1", "pistes": ["inventaire_tournant", "stock_moves"], "ordre": [...]},
      {"groupe": "grp2", "pistes": ["historique_moves"], "ordre": [...]},
      {"groupe": "grp3", "pistes": ["etats_journaliers"], "ordre": [...]}
    ]
  }
Si aucun fork n'est detecte, "setup" est absent/vide.

Usage :
  python regrouper_pistes.py --module=hr_shoorah_demande [--pistes=id1,id2,...]

--pistes= : restreint TOUT le calcul (forks + groupes) a cette selection de
pistes (celles cochees par l'utilisateur, individuellement ou via un raccourci
de groupe). Une dependance vers une piste NON selectionnee est retiree (avec
avertissement) plutot que de bloquer la selection.
"""

import sys
import os
import json
from collections import defaultdict, deque

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTRATS_DIR = os.path.join(ROOT, "contrats")


def parser_pistes(resume_text):
    """Extrait les pistes (id, nom, depends_on) depuis la section === PISTES ===."""
    pistes = {}
    if "=== PISTES ===" not in resume_text:
        return pistes

    apres = resume_text.split("=== PISTES ===", 1)[1]
    for ligne in apres.splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("(") or ligne.startswith("=="):
            continue
        if "|" not in ligne:
            continue
        parts = ligne.split("|")
        piste_id = parts[0].strip()
        nom = parts[1].strip() if len(parts) > 1 else piste_id
        depends_raw = parts[2].strip() if len(parts) > 2 else ""
        depends_on = [d.strip() for d in depends_raw.split(",") if d.strip()]
        if piste_id:
            pistes[piste_id] = {"nom": nom, "depends_on": depends_on}

    return pistes


def filtrer_selection(pistes, selection):
    """Restreint le dictionnaire de pistes a la selection utilisateur. Les
    dependances vers des pistes NON selectionnees sont retirees (avec un
    avertissement), pas bloquantes."""
    if not selection:
        return pistes

    selection_set = set(selection)
    inconnues = selection_set - set(pistes.keys())
    if inconnues:
        print(f"[regrouper_pistes] ⚠️  Selection contient des ids inconnus (ignores) : "
              f"{sorted(inconnues)}", file=sys.stderr)

    resultat = {}
    for pid in selection_set & set(pistes.keys()):
        info = pistes[pid]
        deps_gardees = [d for d in info["depends_on"] if d in selection_set]
        deps_retirees = [d for d in info["depends_on"] if d not in selection_set]
        if deps_retirees:
            print(f"[regrouper_pistes] ⚠️  '{pid}' depend de {deps_retirees}, non "
                  f"selectionnes — dependance ignoree (donnees prealables potentiellement "
                  f"absentes).", file=sys.stderr)
        resultat[pid] = {"nom": info["nom"], "depends_on": deps_gardees}

    return resultat


def _dependents_directs(pistes):
    """dependents[p] = liste des pistes qui dependent DIRECTEMENT de p."""
    dependents = defaultdict(list)
    for pid, info in pistes.items():
        for dep in info["depends_on"]:
            if dep in pistes:
                dependents[dep].append(pid)
    return dependents


def _downstream(pid, dependents):
    """Ensemble des pistes qui dependent (transitivement) de pid."""
    vus = set()
    queue = deque(dependents.get(pid, []))
    while queue:
        p = queue.popleft()
        if p in vus:
            continue
        vus.add(p)
        queue.extend(dependents.get(p, []))
    return vus


def detecter_forks(pistes):
    """
    Une piste F est un FORK si au moins 2 de ses dependants directs sont sur
    des branches VRAIMENT independantes (ni l'un ni l'autre ne depend de
    l'autre, meme transitivement). Ces pistes partent en phase "setup".
    """
    dependents = _dependents_directs(pistes)
    downstream_cache = {pid: _downstream(pid, dependents) for pid in pistes}

    forks = set()
    for pid, deps_directs in dependents.items():
        if len(deps_directs) < 2:
            continue
        independant_trouve = False
        for i in range(len(deps_directs)):
            for j in range(i + 1, len(deps_directs)):
                a, b = deps_directs[i], deps_directs[j]
                relies = (b in downstream_cache.get(a, set())) or (a in downstream_cache.get(b, set()))
                if not relies:
                    independant_trouve = True
                    break
            if independant_trouve:
                break
        if independant_trouve:
            forks.add(pid)

    return forks


def ordonner_topologique(sous_ensemble, pistes):
    """Tri topologique simple sur un sous-ensemble de pistes (dependances
    limitees a l'interieur de ce sous-ensemble)."""
    ids = set(sous_ensemble)
    graphe = {pid: [d for d in pistes[pid]["depends_on"] if d in ids] for pid in ids}
    in_degree = {pid: 0 for pid in ids}
    successeurs = defaultdict(list)
    for pid, deps in graphe.items():
        for d in deps:
            successeurs[d].append(pid)
            in_degree[pid] += 1

    queue = deque(sorted([pid for pid in ids if in_degree[pid] == 0]))
    ordre = []
    while queue:
        pid = queue.popleft()
        ordre.append(pid)
        for suivant in sorted(successeurs[pid]):
            in_degree[suivant] -= 1
            if in_degree[suivant] == 0:
                queue.append(suivant)

    if len(ordre) != len(ids):
        restants = [p for p in ids if p not in ordre]
        print(f"[regrouper_pistes] ⚠️  Cycle detecte dans {sorted(ids)} — ordre partiel",
              file=sys.stderr)
        ordre.extend(sorted(restants))

    return ordre


def regrouper_branches(pistes_branches, forks):
    """
    Union-find sur les pistes NON-fork uniquement, en IGNORANT les aretes qui
    pointent vers un fork (deja resolues par le setup) — c'est ce qui revele
    les vraies branches paralleles independantes.
    """
    parent = {pid: pid for pid in pistes_branches}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for pid, info in pistes_branches.items():
        for dep in info["depends_on"]:
            if dep in forks:
                continue  # resolu par le setup, n'entraine pas de fusion
            if dep in pistes_branches:
                union(pid, dep)

    groupes_bruts = defaultdict(list)
    for pid in pistes_branches:
        groupes_bruts[find(pid)].append(pid)

    resultat = []
    for i, (racine, pids) in enumerate(sorted(groupes_bruts.items()), start=1):
        ordre = ordonner_topologique(pids, pistes_branches)
        resultat.append({"groupe": f"grp{i}", "pistes": ordre, "ordre": ordre})

    return resultat


def etendre_avec_ancetres(forks, pistes):
    """
    Ferme l'ensemble 'forks' par ses ANCETRES (dependances, meme transitives)
    meme si ces ancetres ne sont pas eux-memes des forks. Necessaire car un
    membre du setup peut dependre d'une piste qui, seule, n'a qu'un seul
    dependant (donc pas detectee comme fork) -> sans cette extension, cette
    piste finirait dans une branche executee APRES le setup, alors que le
    setup en a besoin AVANT. Ex: 'produits' (fork, car partage par plusieurs
    branches independantes) depend de 'referentiels' (un seul dependant :
    produits) -> 'referentiels' doit rejoindre le setup, sinon l'ordre est
    casse (produits testerait avant que referentiels ait cree ses donnees).
    """
    etendu = set(forks)
    a_traiter = list(forks)
    while a_traiter:
        pid = a_traiter.pop()
        for dep in pistes.get(pid, {}).get("depends_on", []):
            if dep in pistes and dep not in etendu:
                etendu.add(dep)
                a_traiter.append(dep)
    return etendu


def calculer(pistes):
    """Calcule la structure finale {setup, groupes} a partir des pistes."""
    if not pistes:
        return {"setup": None, "groupes": [{"groupe": "tout", "pistes": [], "ordre": []}]}

    forks_bruts = detecter_forks(pistes)
    forks = etendre_avec_ancetres(forks_bruts, pistes) if forks_bruts else forks_bruts

    ajoutes_pour_ordre = forks - forks_bruts
    if ajoutes_pour_ordre:
        noms_ajoutes = [pistes[p]["nom"] for p in ajoutes_pour_ordre]
        print(f"[regrouper_pistes] ➕ Ajoutees au setup (prerequis d'un membre du setup, "
              f"pas partagees elles-memes) : {sorted(ajoutes_pour_ordre)} ({', '.join(noms_ajoutes)})",
              file=sys.stderr)

    if forks:
        ordre_setup = ordonner_topologique(forks, pistes)
        setup = {"pistes": ordre_setup}
        noms = [pistes[p]["nom"] for p in ordre_setup]
        print(f"[regrouper_pistes] 🏗️  SETUP (fondations partagees, execute une fois) : "
              f"{' -> '.join(ordre_setup)} ({', '.join(noms)})", file=sys.stderr)
    else:
        setup = None
        print("[regrouper_pistes] ℹ️  Aucune fondation partagee detectee — pas de phase setup.",
              file=sys.stderr)

    pistes_branches = {pid: info for pid, info in pistes.items() if pid not in forks}
    groupes = regrouper_branches(pistes_branches, forks)

    for g in groupes:
        noms = [pistes[p]["nom"] for p in g["ordre"]]
        print(f"[regrouper_pistes] {g['groupe']} : {' -> '.join(g['ordre'])} ({', '.join(noms)})",
              file=sys.stderr)

    return {"setup": setup, "groupes": groupes}


def main():
    module = None
    selection = None
    for arg in sys.argv[1:]:
        if arg.startswith("--module="):
            module = arg.split("=", 1)[1].strip()
        elif arg.startswith("--pistes="):
            valeur = arg.split("=", 1)[1].strip()
            selection = [p.strip() for p in valeur.split(",") if p.strip()] or None

    if not module:
        print("Usage: python regrouper_pistes.py --module=<nom_module> [--pistes=id1,id2,...]",
              file=sys.stderr)
        sys.exit(1)

    resume_path = os.path.join(CONTRATS_DIR, f"{module}_resume.md")
    if not os.path.exists(resume_path):
        print(f"[regrouper_pistes] ❌ Resume introuvable : {resume_path}", file=sys.stderr)
        print(json.dumps({"setup": None, "groupes": [{"groupe": "tout", "pistes": [], "ordre": []}]}))
        sys.exit(0)

    with open(resume_path, encoding="utf-8") as f:
        resume_text = f.read()

    pistes = parser_pistes(resume_text)

    if selection:
        print(f"[regrouper_pistes] 🎯 Filtre utilisateur actif : {selection}", file=sys.stderr)
        pistes = filtrer_selection(pistes, selection)

    resultat = calculer(pistes)
    print(json.dumps(resultat))


if __name__ == "__main__":
    main()
