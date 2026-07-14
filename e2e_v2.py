# -*- coding: utf-8 -*-
"""
e2e_v2.py — Orchestrateur E2E v2 (Contrat JSON + ast + formulaire)
===================================================================

Nouvelle architecture "token-efficient" :
  - PASSE 1 (ce fichier, pour l'instant) : Claude lit le code du module et
    genere un CONTRAT JSON (fiche resumee testable) + un RESUME lisible + des
    QUESTIONS. Le Contrat est sauvegarde ; le resume + questions serviront
    plus tard a alimenter le formulaire (ngrok).
  - PASSE 2 (a venir) : teste a partir du Contrat via Playwright, en allant
    chercher le code exact d'une methode avec ast_tool si besoin.

Ce fichier est SEPARE de e2e.py. Un probleme ici n'affecte pas e2e.py.

Usage (local, pour tester la passe 1) :
  python e2e_v2.py --analyze --module=hr_shoorah_demande

Ce que ca produit :
  - contrats/<module>_contrat.json   (le Contrat, sauvegarde)
  - contrats/<module>_resume.md      (le resume + questions, sauvegarde)
  - affiche le resume dans la console
"""

import subprocess
import sys
import os
import re
import json
import shutil
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

ROOT = os.path.dirname(os.path.abspath(__file__))
EXTENSIONS_CIBLES = {".py", ".xml"}   # passe 1 : on se concentre sur models + vues
MAX_TAILLE_FICHIER = 200000           # 200 KB (hr_payslip.py est gros)

CONTRATS_DIR = os.path.join(ROOT, "contrats")
REPORTS_DIR = os.path.join(ROOT, "reports")

# ── Odoo (pour le mode --run : Playwright pilote cette instance) ──────────────
ODOO_URL = os.environ.get("ODOO_URL", "http://185.158.132.243:9019/")
ODOO_DB = os.environ.get("ODOO_DB", "SHOORAH_TEST_2026-07-01_16-07-52")
ODOO_EMAIL = os.environ.get("ODOO_EMAIL", "admin@shoorah")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "")

# URL de login qui FORCE la base (evite que Playwright tombe sur une autre base
# comme SHOORAH_PAIE_TEST). On retire un eventuel '/' final avant de concatener.
ODOO_LOGIN_URL = ODOO_URL.rstrip("/") + f"/web/login?db={ODOO_DB}"

# ── GitHub (pour poster le rapport dans une issue) ────────────────────────────
GITHUB_REPO = os.environ.get("GITHUB_REPO", "Daisy-Consulting/shoorah_test")
GITHUB_ISSUE_NUMBER = int(os.environ.get("GITHUB_ISSUE_NUMBER", "6"))

# ── Type de projet : a-t-il une API mobile a tester ? ─────────────────────────
# true  -> le module expose une API mobile (endpoints /xxx/mobile/*) : on teste
#          ces endpoints comme un vrai client mobile les appelle (RPC/HTTP), EN PLUS de l'UI.
# false -> pas de mobile : on teste via l'interface (UI) uniquement.
# Se regle par projet (variable d'environnement / script de config), le code ne change pas.
TEST_API_MOBILE = os.environ.get("TEST_API_MOBILE", "false").lower() == "true"

# Modules Odoo standard : on ne descend pas dedans (leurs fichiers ne sont pas
# dans ton repo de toute facon), on les ignore comme dependances.
MODULES_STANDARD = {
    'base', 'mail', 'account', 'stock', 'sale', 'purchase',
    'hr', 'project', 'mrp', 'product', 'uom', 'web', 'board',
    'sale_management', 'purchase_stock', 'account_accountant',
    'stock_account', 'hr_expense', 'analytic', 'digest',
    'hr_holidays', 'hr_attendance', 'hr_contract', 'resource',
}


# ══════════════════════════════════════════════════════════════════════════════
# COLLECTE DES FICHIERS DU MODULE
# (logique reprise de claude_review_gha.py, adaptee)
# ══════════════════════════════════════════════════════════════════════════════

def collecter_fichiers_dossier(dossier):
    """Liste les .py/.xml d'un dossier module, en ignorant les dossiers inutiles."""
    fichiers = []
    DOSSIERS_EXCLUS = {'__pycache__', 'static', 'tests', 'node_modules', '.git'}
    for root, dirs, files in os.walk(dossier):
        dirs[:] = [d for d in dirs if d not in DOSSIERS_EXCLUS]
        for f in files:
            if os.path.splitext(f)[1] in EXTENSIONS_CIBLES:
                chemin = os.path.relpath(os.path.join(root, f), ROOT)
                fichiers.append(chemin)
    return fichiers


def trouver_module(nom):
    """Trouve le dossier d'un module par son nom (celui qui a un __manifest__.py)."""
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in {'__pycache__', '.git', 'node_modules'}]
        if os.path.basename(root) == nom and '__manifest__.py' in files:
            return root
    return None


def get_fichiers_module(nom_module):
    """
    Trouve le module et collecte ses fichiers .py/.xml.
    NB : pour la passe 1 on ne descend PAS dans les dependances custom
    (on analyse le module cible lui-meme). On les ajoutera plus tard si besoin.
    """
    module_path = trouver_module(nom_module)
    if not module_path:
        print(f"[e2e_v2] ERREUR : module '{nom_module}' introuvable "
              f"(pas de dossier avec __manifest__.py).")
        sys.exit(1)

    print(f"[e2e_v2] Module trouve : {module_path}")
    fichiers = collecter_fichiers_dossier(module_path)

    # separer python et xml pour le prompt.
    # Les .py incluent models ET controllers (les endpoints API sont testables).
    py_files = sorted([f for f in fichiers if f.endswith('.py')
                       and '__manifest__' not in f and '__init__' not in f])
    xml_files = sorted([f for f in fichiers if f.endswith('.xml')])

    # Distinguer controllers pour info (Claude les lit dans tous les cas)
    nb_controllers = len([f for f in py_files if 'controller' in f.replace('\\', '/').lower()])

    print(f"[e2e_v2] Fichiers Python : {len(py_files)}"
          + (f" (dont {nb_controllers} controller(s))" if nb_controllers else ""))
    print(f"[e2e_v2] Fichiers XML    : {len(xml_files)}")
    return module_path, py_files, xml_files


# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE CODE CLI
# ══════════════════════════════════════════════════════════════════════════════

def trouver_claude():
    return (
        shutil.which('claude.cmd')
        or shutil.which('claude')
        or os.path.join(os.environ.get('APPDATA', ''), 'npm', 'claude.cmd')
    )


def appeler_claude(prompt, timeout=1800):
    """
    Lance Claude Code CLI en mode non-interactif, dans le dossier du projet
    (cwd=ROOT) pour qu'il puisse LIRE les fichiers du module lui-meme.
    Retourne le champ 'result' de la sortie JSON.
    """
    claude_exe = trouver_claude()
    if not claude_exe:
        print("[e2e_v2] ERREUR : Claude Code CLI introuvable.")
        print("[e2e_v2] Installez : npm i -g @anthropic-ai/claude-code")
        sys.exit(1)

    # Le prompt est passe via STDIN (pas en argument) : c'est la seule methode
    # sans limite de taille. Pour les gros modules, le prompt (Contrat + scenarios)
    # depassait la limite d'arguments du systeme (OSError Errno 7
    # "Argument list too long") quand on le passait en argument de commande.
    try:
        proc = subprocess.Popen(
            [claude_exe, '-p',
             '--dangerously-skip-permissions', '--output-format', 'json'],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
        )
        print("[e2e_v2] ⏳ Claude analyse le code (peut prendre plusieurs minutes)...")
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"[e2e_v2] TIMEOUT apres {timeout}s")
        return None
    

    if not stdout:
        if stderr:
            print(f"[e2e_v2] STDERR : {stderr[:500]}")
        return None

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print("[e2e_v2] Impossible de parser la sortie JSON de Claude.")
        print(stdout[:500])
        return None

    cout = data.get('total_cost_usd', 0)
    print(f"[e2e_v2] ✅ Analyse terminee — cout : ${cout:.4f}")
    return data.get('result', '').strip()


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT PASSE 1
# ══════════════════════════════════════════════════════════════════════════════

def construire_prompt_passe1(module_name, py_files, xml_files):
    liste_py = "\n".join(f"  - {f}" for f in py_files) or "  (aucun)"
    liste_xml = "\n".join(f"  - {f}" for f in xml_files) or "  (aucun)"

    return f"""Tu es un ingenieur QA senior expert Odoo. Ta mission : analyser le module
Odoo "{module_name}" et produire un CONTRAT DE TEST structure, en vue d'un test
fonctionnel exhaustif (validation avant livraison client).

== FICHIERS A LIRE (lis CHACUN avec ton outil de lecture de fichiers) ==

Fichiers Python (modeles) :
{liste_py}

Fichiers XML (vues) :
{liste_xml}

== REGLES D'ANALYSE (IMPORTANTES) ==
1. IGNORE tout code COMMENTE. Ne considere que la logique ACTIVE (executee).
   Certains fichiers contiennent plusieurs versions commentees d'une meme
   methode : seule la version non commentee compte.
2. Pour un modele HERITE (_inherit), ne decris QUE ce que ce module AJOUTE ou
   MODIFIE, pas tout le modele Odoo standard.
3. Croise les modeles (.py) avec les vues (.xml) : pour chaque element
   testable, indique OU il apparait dans l'interface (formulaire, liste,
   bouton, onglet) si tu peux le deduire des vues.
4. IMPORTANT - "source_method" : ce champ doit contenir UNIQUEMENT un nom de
   methode Python reelle (ex: "action_approve", "_compute_schedule_count"),
   car un outil ira chercher ce code exact plus tard. Ne mets JAMAIS un nom de
   fichier dedans.
   - Si l'element vient d'une methode Python -> "source_method": "<nom_methode>"
   - Si l'element n'a PAS de methode Python (champ related, regle de visibilite
     XML, decoration de vue) -> "source_method": null ET "source_file": "<fichier>"
   Ex champ calcule : {{"field": "x", "source_method": "_compute_x", "source_file": null}}
   Ex regle de vue  : {{"field": "y", "source_method": null, "source_file": "vues.xml"}}
   Ex related field : {{"field": "z", "source_method": null, "source_file": "modele.py"}}

== CE QUE TU DOIS PRODUIRE (ECRIS DIRECTEMENT 2 FICHIERS) ==
IMPORTANT : n'affiche PAS le contenu dans ta reponse. Utilise ton outil
d'ecriture de fichiers pour CREER directement les 2 fichiers suivants sur le
disque (le dossier "contrats/" existe deja, cree-le sinon) :

FICHIER 1 : contrats/{module_name}_contrat.json
  -> le CONTRAT en JSON pur, valide, structure par modele. Schema attendu :

{{
  "module": "{module_name}",
  "models": [
    {{
      "model": "<nom.modele.odoo>",
      "inherited": true/false,
      "has_ui": true/false,
      "is_payroll": true/false,
      "test_level": 1,
      "states_field": "<champ d'etat ou null>",
      "states": ["..."],
      "state_transitions": [
        {{"from": "...", "to": "...", "trigger": "<methode>", "source_method": "<methode>"}}
      ],
      "constraints": [
        {{"rule": "...", "expected_error": "...", "source_method": "<methode>"}}
      ],
      "status_rules": [
        {{"condition": "...", "expected": "...", "source_method": "<methode ou null>", "source_file": "<fichier si pas de methode, sinon null>"}}
      ],
      "computed_fields": [
        {{"field": "...", "rule": "...", "source_method": "<methode ou null>", "source_file": "<fichier si pas de methode, sinon null>", "is_amount": true/false}}
      ],
      "onchange": [
        {{"trigger_field": "...", "effect": "...", "source_method": "<methode>"}}
      ],
      "view_rules": [
        {{"field": "...", "rule": "...", "type": "conditional_visibility|required_by_view", "source": "<fichier.xml>"}}
      ],
      "actions": [
        {{"method": "...", "effect": "...", "preconditions": ["..."], "expected_errors": ["..."], "ui_testable": true/false, "needs_human_check": "<question ou absent>"}}
      ],
      "overridden_methods": [
        {{"method": "...", "changed_behavior": "...", "expected_error": "...", "ui_testable": true/false}}
      ],
      "file_exports": [
        {{"method": "...", "effect": "...", "ui_testable": "declenchement seulement"}}
      ],
      "amount_checks_required": ["<champs de montant a verifier>"],
      "internal_methods": [
        {{"method": "...", "note": "non-UI"}}
      ]
    }}
  ],
  "open_questions": ["<questions transverses pour l'humain>"]
}}

Regles pour le JSON :
- Une section (ex: state_transitions) n'apparait QUE si le modele la contient.
- test_level : 1 = approfondi, 2 = standard, 3 = minimal (technique sans UI).
- is_payroll = true si le modele calcule des montants de salaire/cotisations.
- needs_human_check / open_questions : tout ce que tu ne peux pas trancher seul
  depuis le code (valeurs en dur, taux, montants, intention ambigue). MAX 8 questions.

FICHIER 2 : contrats/{module_name}_resume.md
  -> un RESUME LISIBLE en francais simple, court, au format exact :

=== RESUME — Module {module_name} ===
(2-4 phrases : ce que fait le module, combien de modeles, ce qui est testable)

MODELES PRINCIPAUX :
- <modele> : <ce qu'il fait en 1 ligne> (<nb boutons>, <nb regles>...)

=== MES QUESTIONS (reponds sous chaque question) ===
Q1. ...
   ->
Q2. ...
   ->

=== ZONE LIBRE — ajoute / corrige / precise ce que tu veux ===
(laisse cette zone vide, l'humain la remplira)

=== PISTES ===
(Regroupe les elements testables du module en PISTES logiques, selon la logique
metier du code — par exemple : partie application mobile, workflow d'une demande,
effets RH, calculs de paie, contraintes de securite... Deduis ces pistes toi-meme
en comprenant le code, ne te limite pas a des mots-cles. Il peut y en avoir 2, 5,
10 selon le module. Ecris UNE piste par ligne, au format exact "id|nom" ou :
  - id  = identifiant court en minuscules sans espace (ex: mobile, demande, rh, paie)
  - nom = libelle lisible court (ex: API Mobile, Workflow de la demande)
Exemple :
mobile|API Mobile (routes /hr/mobile/*)
demande|Workflow de la demande (draft->approved->done)
rh|Effets RH (conges, planning)
N'ajoute rien d'autre dans cette section : seulement les lignes "id|nom".)

== APRES AVOIR ECRIT LES 2 FICHIERS ==
Reponds UNIQUEMENT par une ligne de confirmation, par exemple :
"OK - 2 fichiers ecrits : contrats/{module_name}_contrat.json ({{N}} modeles) et contrats/{module_name}_resume.md"
N'affiche NI le JSON NI le resume dans ta reponse — ils sont deja dans les fichiers.
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# PARSING & SAUVEGARDE
# ══════════════════════════════════════════════════════════════════════════════

def extraire_json(texte):
    """
    Extrait le premier objet JSON valide du texte (la partie Contrat).
    Robuste face aux parasites : preambule (meme en langue etrangere),
    blocs markdown ```json ... ```, et accolades a l'interieur des chaines.
    """
    # 1) Retirer les fences markdown ```json / ``` si presentes
    t = texte.replace('```json', '').replace('```JSON', '').replace('```', '')

    debut = t.find('{')
    if debut == -1:
        return None, "Aucun '{' trouve dans la partie Contrat."

    # 2) Parcours en comptant la profondeur, MAIS en ignorant tout ce qui est
    #    entre guillemets (une accolade dans une valeur texte ne compte pas).
    profondeur = 0
    dans_chaine = False
    echappe = False
    for i in range(debut, len(t)):
        c = t[i]
        if dans_chaine:
            if echappe:
                echappe = False
            elif c == '\\':
                echappe = True
            elif c == '"':
                dans_chaine = False
            continue
        # hors chaine
        if c == '"':
            dans_chaine = True
        elif c == '{':
            profondeur += 1
        elif c == '}':
            profondeur -= 1
            if profondeur == 0:
                bloc = t[debut:i + 1]
                try:
                    return json.loads(bloc), None
                except json.JSONDecodeError as e:
                    return None, f"JSON invalide : {e}"
    return None, "Accolade fermante manquante (JSON incomplet)."


def traiter_reponse(module_name, reponse):
    """
    Verifie que Claude Code a bien ECRIT les 2 fichiers (contrat + resume).
    Valide le JSON du contrat. Si les fichiers n'existent pas (Claude a mis le
    contenu dans sa reponse au lieu d'ecrire), on retombe sur l'extraction.
    """
    os.makedirs(CONTRATS_DIR, exist_ok=True)
    contrat_path = os.path.join(CONTRATS_DIR, f"{module_name}_contrat.json")
    resume_path = os.path.join(CONTRATS_DIR, f"{module_name}_resume.md")

    # ── Cas nominal : Claude a ECRIT le fichier contrat ──────────────────────
    if os.path.exists(contrat_path):
        try:
            with open(contrat_path, encoding="utf-8") as f:
                contrat = json.load(f)
            nb_models = len(contrat.get("models", []))
            nb_questions = len(contrat.get("open_questions", []))
            print(f"[e2e_v2] ✅ Contrat ecrit par Claude : {contrat_path}")
            print(f"[e2e_v2]    -> {nb_models} modele(s), {nb_questions} question(s)")
            resume = ""
            if os.path.exists(resume_path):
                with open(resume_path, encoding="utf-8") as f:
                    resume = f.read().strip()
                print(f"[e2e_v2] ✅ Resume ecrit par Claude : {resume_path}")
            else:
                print(f"[e2e_v2] ⚠️  Resume manquant (le formulaire sera limite).")
            return resume, contrat
        except json.JSONDecodeError as e:
            print(f"[e2e_v2] ⚠️  Le fichier contrat existe mais JSON invalide : {e}")
            # on tente le fallback ci-dessous

    # ── Fallback : Claude a mis le contenu dans sa reponse (ancien comportement) ─
    print("[e2e_v2] ℹ️  Fichier contrat absent — tentative d'extraction depuis la reponse.")
    if "---RESUME---" in reponse:
        partie_json, partie_resume = reponse.split("---RESUME---", 1)
    else:
        partie_json = reponse
        partie_resume = ""

    contrat, err = extraire_json(partie_json)

    if partie_resume.strip():
        with open(resume_path, "w", encoding="utf-8") as f:
            f.write(partie_resume.strip())

    if contrat is None:
        print(f"[e2e_v2] ❌ Contrat introuvable ET non extractible : {err}")
        brut_path = os.path.join(CONTRATS_DIR, f"{module_name}_brut.txt")
        with open(brut_path, "w", encoding="utf-8") as f:
            f.write(reponse)
        print(f"[e2e_v2] Reponse brute sauvegardee pour debug : {brut_path}")
        return partie_resume.strip(), None

    with open(contrat_path, "w", encoding="utf-8") as f:
        json.dump(contrat, f, indent=2, ensure_ascii=False)
    nb_models = len(contrat.get("models", []))
    print(f"[e2e_v2] ✅ Contrat recupere par extraction : {contrat_path} ({nb_models} modeles)")
    return partie_resume.strip(), contrat


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def analyser_module(module_name, force=True):
    """
    Passe 1 : genere le Contrat.
    Si force=False ET qu'un Contrat existe deja, on le REUTILISE (skip)
    pour economiser tokens+temps quand le module n'a pas change.
    """
    contrat_path = os.path.join(CONTRATS_DIR, f"{module_name}_contrat.json")

    # ── Reutilisation du Contrat existant (Option A) ─────────────────────────
    if not force and os.path.exists(contrat_path):
        import time
        mtime = os.path.getmtime(contrat_path)
        date_gen = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
        print(f"\n[e2e_v2] ♻️  Reutilisation du Contrat existant "
              f"(genere le {date_gen})")
        print(f"[e2e_v2] ⚠️  Si le code a change depuis, relance avec "
              f"--analyze (regeneration) pour un Contrat a jour.")
        print(f"[e2e_v2] Contrat : {contrat_path}")
        return

    print(f"\n[e2e_v2] ═══ PASSE 1 — Analyse du module '{module_name}' ═══\n")

    module_path, py_files, xml_files = get_fichiers_module(module_name)
    if not py_files and not xml_files:
        print("[e2e_v2] Aucun fichier .py/.xml a analyser.")
        return

    prompt = construire_prompt_passe1(module_name, py_files, xml_files)
    reponse = appeler_claude(prompt)

    if not reponse:
        print("[e2e_v2] ❌ Pas de reponse exploitable de Claude.")
        return

    resume, contrat = traiter_reponse(module_name, reponse)

    print("\n" + "=" * 70)
    print("RESUME (a valider) :")
    print("=" * 70)
    print(resume)
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# RAFRAICHIR LE RESUME (mode --refresh-resume)
# Regenere UNIQUEMENT le resume + questions + pistes A PARTIR DU JSON EXISTANT
# (pas en relisant tout le code). Petit appel, pas cher. Le JSON n'est PAS touche.
# Utile quand le Contrat existe deja mais que le resume n'a pas encore les pistes.
# ══════════════════════════════════════════════════════════════════════════════

def construire_prompt_refresh_resume(module_name, contrat):
    contrat_json = json.dumps(contrat, indent=2, ensure_ascii=False)
    return f"""Tu es un ingenieur QA senior expert Odoo. Voici le CONTRAT DE TEST (JSON)
du module "{module_name}", deja genere a partir du code. Ta mission : produire
UNIQUEMENT le RESUME lisible + les QUESTIONS + les PISTES, a partir de ce Contrat
(tu n'as PAS besoin de relire le code : tout est dans le Contrat ci-dessous).

== CONTRAT (source de verite) ==
{contrat_json}

== CE QUE TU DOIS PRODUIRE (ECRIS DIRECTEMENT 1 FICHIER) ==
IMPORTANT : n'affiche PAS le contenu dans ta reponse. Utilise ton outil d'ecriture
de fichiers pour CREER directement le fichier suivant (le dossier "contrats/"
existe deja) :

FICHIER : contrats/{module_name}_resume.md
  -> au format EXACT suivant :

=== RESUME — Module {module_name} ===
(2-4 phrases : ce que fait le module, combien de modeles, ce qui est testable)

MODELES PRINCIPAUX :
- <modele> : <ce qu'il fait en 1 ligne>

=== MES QUESTIONS (reponds sous chaque question) ===
Q1. ...
   ->
Q2. ...
   ->
(reprends ici les open_questions du Contrat + toute ambiguite metier ; MAX 8)

=== ZONE LIBRE — ajoute / corrige / precise ce que tu veux ===
(laisse cette zone vide, l'humain la remplira)

=== PISTES ===
(Regroupe les elements testables du module en PISTES logiques, selon la logique
metier visible dans le Contrat — par exemple : partie application mobile, workflow
d'une demande, effets RH, calculs de paie, contraintes de securite... Deduis ces
pistes toi-meme. Il peut y en avoir 2, 5, 10. Ecris UNE piste par ligne, au format
exact "id|nom" ou :
  - id  = identifiant court en minuscules sans espace (ex: mobile, demande, rh, paie)
  - nom = libelle lisible court (ex: API Mobile, Workflow de la demande)
Exemple :
mobile|API Mobile (routes /hr/mobile/*)
demande|Workflow de la demande (draft->approved->done)
rh|Effets RH (conges, planning)
N'ajoute rien d'autre dans cette section : seulement les lignes "id|nom".)

== APRES AVOIR ECRIT LE FICHIER ==
Reponds UNIQUEMENT par une ligne de confirmation, ex :
"OK - resume ecrit : contrats/{module_name}_resume.md"
N'affiche PAS le resume dans ta reponse.
""".strip()


def rafraichir_resume(module_name):
    """
    Regenere le resume (+ questions + pistes) a partir du JSON existant.
    Le Contrat JSON n'est PAS regenere ni modifie. Appel court = peu couteux.
    """
    print(f"\n[e2e_v2] ═══ RAFRAICHIR LE RESUME — module '{module_name}' ═══\n")

    contrat_path = os.path.join(CONTRATS_DIR, f"{module_name}_contrat.json")
    if not os.path.exists(contrat_path):
        print(f"[e2e_v2] ❌ Contrat introuvable : {contrat_path}")
        print(f"[e2e_v2] Lance d'abord : python e2e_v2.py --analyze --module={module_name}")
        return

    with open(contrat_path, encoding='utf-8') as f:
        contrat = json.load(f)
    nb_models = len(contrat.get("models", []))
    print(f"[e2e_v2] Contrat charge ({nb_models} modeles) — le JSON ne sera PAS modifie.")

    prompt = construire_prompt_refresh_resume(module_name, contrat)
    reponse = appeler_claude(prompt)

    if not reponse:
        print("[e2e_v2] ❌ Pas de reponse exploitable de Claude.")
        return

    resume_path = os.path.join(CONTRATS_DIR, f"{module_name}_resume.md")

    # Cas nominal : Claude a ecrit le resume directement.
    if os.path.exists(resume_path):
        with open(resume_path, encoding='utf-8') as f:
            resume = f.read().strip()
        has_pistes = "=== PISTES ===" in resume
        print(f"[e2e_v2] ✅ Resume rafraichi : {resume_path}")
        print(f"[e2e_v2]    Section PISTES presente : {'oui' if has_pistes else 'NON (a verifier)'}")
    else:
        # Fallback : Claude a mis le resume dans sa reponse -> on l'ecrit nous-memes.
        with open(resume_path, "w", encoding='utf-8') as f:
            f.write(reponse.strip())
        print(f"[e2e_v2] ✅ Resume rafraichi (depuis la reponse) : {resume_path}")

    print("\n" + "=" * 70)
    print("RESUME RAFRAICHI :")
    print("=" * 70)
    with open(resume_path, encoding='utf-8') as f:
        print(f.read())
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# PASSE 2 (mode --generate-scenarios) : generer les SCENARIOS de test
# a partir du Contrat, SANS encore les executer via Playwright.
# But : valider que les tests que Claude compte faire sont pertinents.
# ══════════════════════════════════════════════════════════════════════════════

def charger_contrat(module_name):
    """Charge le Contrat JSON genere par la passe 1. Charge aussi les
    reponses humaines (formulaire) si elles existent, pour les injecter."""
    contrat_path = os.path.join(CONTRATS_DIR, f"{module_name}_contrat.json")
    if not os.path.exists(contrat_path):
        print(f"[e2e_v2] ❌ Contrat introuvable : {contrat_path}")
        print(f"[e2e_v2] Lance d'abord : python e2e_v2.py --analyze --module={module_name}")
        return None, None

    with open(contrat_path, encoding='utf-8') as f:
        contrat = json.load(f)

    # Reponses humaines (issues du formulaire) : optionnelles pour l'instant.
    reponses = None
    reponses_path = os.path.join(CONTRATS_DIR, f"{module_name}_reponses.md")
    if os.path.exists(reponses_path):
        with open(reponses_path, encoding='utf-8') as f:
            reponses = f.read().strip()
        if reponses:
            print(f"[e2e_v2] Reponses humaines chargees : {reponses_path}")

    return contrat, reponses


def construire_prompt_scenarios(module_name, contrat, reponses):
    """
    Prompt passe 2 (mode scenarios) : a partir du Contrat, Claude genere la
    liste EXHAUSTIVE des scenarios de test qu'il executerait — sans les jouer.
    Si des PISTES ont ete cochees dans le formulaire, on genere UNIQUEMENT les
    scenarios de ces pistes (ciblage / economie).
    """
    contrat_json = json.dumps(contrat, indent=2, ensure_ascii=False)

   # ── Detecter les pistes choisies (section ajoutee par le formulaire) ──────
    pistes_choisies = ""
    if reponses and "=== PISTES CHOISIES ===" in reponses:
        apres = reponses.split("=== PISTES CHOISIES ===", 1)[1]
        # On prend TOUTES les lignes non vides (une piste cochee peut etre
        # sur sa propre ligne quand plusieurs pistes sont selectionnees).
        lignes_pistes = [l.strip() for l in apres.splitlines() if l.strip()]
        pistes_choisies = ", ".join(lignes_pistes)

    bloc_reponses = ""
    if reponses:
        bloc_reponses = f"""
== REPONSES / CORRECTIONS DE L'HUMAIN (FONT AUTORITE) ==
Ces precisions viennent de la personne qui connait le metier. Si elles
contredisent ta comprehension du code, SUIS L'HUMAIN.
{reponses}
"""

    # ── Bloc de ciblage : si des pistes sont cochees, on limite la generation ─
    bloc_pistes = ""
    if pistes_choisies:
        bloc_pistes = f"""
== PERIMETRE CIBLE — PISTES CHOISIES (IMPERATIF) ==
La personne a choisi de ne tester QUE la/les piste(s) suivante(s) :
  {pistes_choisies}

Ces pistes correspondent aux regroupements logiques que TU as toi-meme definis
lors de l'analyse (section PISTES). Tu dois donc :
  - Generer UNIQUEMENT les scenarios qui relevent de ces pistes.
  - IGNORER completement tout ce qui ne fait pas partie de ces pistes (ne genere
    aucun scenario pour les autres parties du module).
  - Si un element du Contrat n'appartient a aucune piste cochee, ne le teste pas.
En cas de doute sur l'appartenance d'un element a une piste, rattache-le a la
piste la plus logique et ne genere ses scenarios QUE si cette piste est cochee.
"""

    # ── Bloc PERIMETRE : depend du type de projet (mobile ou non) ─────────────
    if TEST_API_MOBILE:
        bloc_perimetre = """== PERIMETRE : QA FONCTIONNELLE (UI + API MOBILE) ==
Ce module expose une API mobile (endpoints HTTP/JSON de type /xxx/mobile/*).
On valide le fonctionnel tel qu'il est reellement utilise :
  - Teste l'interface (UI) : boutons, formulaires, vues, transitions.
  - Teste AUSSI les endpoints de l'API mobile, comme le ferait un vrai client
    mobile : appels HTTP/JSON (RPC) vers les routes mobile DOCUMENTEES du module,
    avec des donnees valides et invalides, pour verifier les reponses, la gestion
    d'erreurs et la coherence des donnees.
Ces appels API sont le mode de fonctionnement NORMAL de l'app mobile — c'est du
test fonctionnel, pas un audit de securite. Reste sur les endpoints prevus du
module ; ne cherche pas a contourner les restrictions de l'UI back-office ni a
forcer des methodes internes hors des chemins prevus."""
    else:
        bloc_perimetre = """== PERIMETRE : QA FONCTIONNELLE UNIQUEMENT (VIA L'UI) ==
On teste le comportement FONCTIONNEL du module tel qu'un utilisateur l'utilise
via l'interface (UI). Donc :
  - Teste UNIQUEMENT via les chemins prevus : boutons, formulaires, vues, actions UI.
  - N'effectue PAS d'appels RPC/ORM directs pour forcer une action hors UI, ni de
    tentative de contourner les restrictions de vue (create=0/delete=0/readonly).
  - Si une action n'est atteignable que par un bouton/menu, teste-la par ce bouton/menu,
    pas en appelant la methode directement.
Le but est de valider que le module marche correctement pour l'utilisateur final.
Reste sur du fonctionnel via l'interface."""

    return f"""Tu es un ingenieur QA senior. Voici le CONTRAT DE TEST du module Odoo
"{module_name}" (genere a partir du code). Ta mission : produire la liste
EXHAUSTIVE des SCENARIOS de test a executer, SANS les executer maintenant.

== CONTRAT DE TEST (source de verite) ==
{contrat_json}
{bloc_reponses}{bloc_pistes}
== CE QUE TU DOIS FAIRE ==
A partir du Contrat (et des reponses humaines si presentes), genere les
scenarios de test necessaires pour une validation avant livraison client.
{"IMPORTANT : limite-toi STRICTEMENT aux pistes cochees ci-dessus." if pistes_choisies else "Genere TOUS les scenarios (aucune piste specifique n'a ete cochee)."}

Couvre systematiquement, pour chaque modele testable (has_ui=true) {"ET faisant partie des pistes cochees" if pistes_choisies else ""} :
  - Chaque transition d'etat (state_transitions), y compris les transitions
    interdites (verifier qu'elles sont bien bloquees).
  - Chaque bouton / action, avec ses pre-conditions ET ses erreurs attendues
    (expected_errors) : il faut un scenario qui declenche CHAQUE erreur.
  - Chaque contrainte (constraints) : un scenario qui la viole exprES.
  - Chaque regle de visibilite (view_rules) : verifier que le champ/bouton
    apparait/disparait selon la condition.
  - Chaque champ calcule (computed_fields) : verifier la valeur produite.
  - Les regles de statut (status_rules).
  - Pour is_payroll=true : verifier les montants (amount_checks_required) —
    signale si tu as besoin de valeurs de reference humaines.

Ajoute aussi une section de scenarios "non evidents" : cas limites, valeurs
nulles, ordre d'actions inhabituel, incoherences — que tu deduis toi-meme{"  (mais toujours dans le perimetre des pistes cochees)" if pistes_choisies else ""}.

{bloc_perimetre}

Ne cherche PAS a executer. Ne te connecte a rien. Liste seulement les scenarios.

== FORMAT DE REPONSE (markdown) ==

## Scenarios de test — {module_name}

### <modele> — <categorie (ex: Transitions d'etat)>
| # | Scenario | Action | Resultat attendu | Reference code |
|---|----------|--------|------------------|----------------|
| 1 | ... | ... | ... | <source_method du Contrat> |

(repete les tableaux par modele et par categorie)

### 🔍 Scenarios non evidents (deduits)
| # | Scenario | Pourquoi c'est un risque | Resultat attendu |
|---|----------|--------------------------|------------------|

### ⚠️ Points bloquants avant test
(liste ici ce qui t'empeche de tester : valeurs de reference manquantes,
questions sans reponse, pre-requis de donnees...)

**Total scenarios : X**

Ne cree aucun fichier. Retourne uniquement ce rapport markdown.
""".strip()


def generer_scenarios(module_name):
    print(f"\n[e2e_v2] ═══ PASSE 2 (scenarios) — module '{module_name}' ═══\n")

    contrat, reponses = charger_contrat(module_name)
    if contrat is None:
        return

    nb_models = len(contrat.get("models", []))
    print(f"[e2e_v2] Contrat charge : {nb_models} modele(s)")

    prompt = construire_prompt_scenarios(module_name, contrat, reponses)
    reponse = appeler_claude(prompt)

    if not reponse:
        print("[e2e_v2] ❌ Pas de reponse exploitable de Claude.")
        return

    # Sauvegarde des scenarios
    os.makedirs(CONTRATS_DIR, exist_ok=True)
    scenarios_path = os.path.join(CONTRATS_DIR, f"{module_name}_scenarios.md")
    with open(scenarios_path, "w", encoding="utf-8") as f:
        f.write(reponse)
    print(f"[e2e_v2] ✅ Scenarios sauvegardes : {scenarios_path}")

    print("\n" + "=" * 70)
    print("SCENARIOS DE TEST (a valider avant execution) :")
    print("=" * 70)
    print(reponse)
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# PASSE 2 (mode --run) : EXECUTER les scenarios via Playwright sur l'instance
# Odoo reelle, en allant lire le code exact via ast_tool quand un bug est trouve.
# Produit un rapport final PASS/FAIL.
# ══════════════════════════════════════════════════════════════════════════════

def construire_prompt_run(module_name, contrat, scenarios, reponses, priority_only=False, max_scenarios=0):
    contrat_json = json.dumps(contrat, indent=2, ensure_ascii=False)

    bloc_filtre = ""
    if priority_only or max_scenarios:
        lignes = ["\n== PERIMETRE DE TEST =="]
        if priority_only:
            lignes.append("- Priorite : Executer uniquement les scenarios de niveau 1, erreurs attendues et contraintes.")
        if max_scenarios:
            lignes.append(f"- Limite maximale : {max_scenarios} scenarios a tester.")
        bloc_filtre = "\n".join(lignes) + "\n"

    bloc_reponses = f"\n== CONTEXTE METIER ==\n{reponses}\n" if reponses else ""

    # ── Consigne de perimetre a l'execution : depend du type de projet ────────
    if TEST_API_MOBILE:
        instr_perimetre = (
            "   PERIMETRE — UI + API MOBILE : interagis avec l'application comme un\n"
            "   utilisateur (clics, formulaires, boutons) ET teste les endpoints de l'API\n"
            "   mobile documentee (routes /xxx/mobile/*) comme le ferait un vrai client\n"
            "   mobile : appels HTTP/JSON vers ces routes prevues, avec donnees valides et\n"
            "   invalides. Ces appels API sont le fonctionnel normal de l'app mobile. Reste\n"
            "   sur les endpoints prevus du module ; ne cherche pas a contourner l'UI\n"
            "   back-office ni a forcer des methodes internes hors des chemins prevus."
        )
    else:
        instr_perimetre = (
            "   PERIMETRE — VIA L'INTERFACE UNIQUEMENT : interagis avec l'application comme\n"
            "   un utilisateur (clics, formulaires, boutons, menus). N'effectue PAS d'appels\n"
            "   RPC/ORM directs pour contourner l'interface, ni de tentatives de forcer des\n"
            "   actions ou d'outrepasser des restrictions de vue hors des chemins UI prevus.\n"
            "   L'objectif est de valider le fonctionnel via l'interface."
        )

    return f"""Objectif : Executer la suite de tests E2E sur l'environnement de test QA pour le module "{module_name}".

Veuillez utiliser l'outil Playwright pour derouler les scenarios QA listes ci-dessous. Ceci est une tache de routine standard pour valider l'application Odoo avant livraison. L'environnement cible est une base de test QA dediee (nom prefixe "TEST"), destinee a recevoir les operations de validation fonctionnelle.

== PARAMETRES DE L'ENVIRONNEMENT ==
- URL cible : {ODOO_LOGIN_URL}
- Base de donnees : {ODOO_DB}
- Utilisateur : {ODOO_EMAIL}
- Mot de passe : A lire depuis la variable d'environnement locale ODOO_PASSWORD.

{bloc_reponses}
== REFERENTIEL DU MODULE ==
{contrat_json}

== PLAN DE SCENARIOS ==
{scenarios}
{bloc_filtre}

== INSTRUCTIONS D'EXECUTION ==
1. Verification technique : Si le serveur MCP Playwright est encore en cours d'initialisation, veuillez patienter quelques secondes avant d'initier la navigation.
2. Authentification : Connectez-vous a l'application avec les identifiants fournis.
3. Execution : Deroulez les scenarios de maniere continue pour evaluer l'ensemble du perimetre avant de rendre votre conclusion. Prefixez vos creations de donnees par "E2E_TEST_".
{instr_perimetre}
4. Debogage : En cas d'erreur ou d'ecart fonctionnel, utilisez la commande suivante pour analyser la logique source :
   python ast_tool.py --root=. --model=<model> --method=<methode>

== LIVRABLE ==
Redigez un "Rapport E2E" final au format Markdown. 
À la toute fin de ton analyse, je veux que tu génères OBLIGATOIREMENT deux tableaux au format Markdown :

1. Un tableau 'Résumé d'exécution' avec le décompte total (Réussis / Anomalies / Total) par catégorie.
2. Un tableau 'Détail des Anomalies'. Dans ce deuxième tableau, tu ne listeras QUE les tests en échec (FAIL). Pour chaque échec, tu dois créer 3 colonnes : 'Nom du Test', 'Scénario Exact' (détaille précisément étape par étape les actions qui ont mené à l'erreur), et 'Cause de l'Erreur' (explique pourquoi ça a planté). 
Important : dans la colonne 'Nom du Test', tu dois obligatoirement inclure le numéro du scénario correspondant entre parenthèses, par exemple : Test Approbation API (5).

Voici la structure stricte attendue pour ces deux tableaux :

### 1. Résumé d'exécution
| Catégorie | Réussis ✅ | Anomalies ❌ | Total |
| :--- | :---: | :---: | :---: |
| Transitions d'état | 13 | 3 | 16 |
| Contraintes | 5 | 0 | 5 |

### 2. Détail des Anomalies (Focus Scénarios)
| Nom du Test | Scénario Exact (Étapes) | Cause de l'Erreur |
| :--- | :--- | :--- |
| **Exemple Test (ID)** | 1. Action 1<br>2. Action 2... | Explication de la cause |

Sous le dernier tableau, ajoutez la mention : **Total : X/Y PASS**
"""

def poster_rapport_github(rapport: str):
    """Poste le rapport comme commentaire dans l'Issue GitHub (reprise de e2e.py)."""
    import requests

    token = None
    env_path = os.path.join(ROOT, '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                if line.startswith('GITHUB_TOKEN='):
                    token = line.strip().split('=', 1)[1]
                    break
    if not token:
        token = os.environ.get('GITHUB_TOKEN')

    if not token:
        print("[e2e_v2] ⚠️  GITHUB_TOKEN manquant — rapport non posté sur GitHub")
        print("[e2e_v2] Rapport local sauvegardé uniquement")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{GITHUB_ISSUE_NUMBER}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {"body": rapport}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        if response.status_code == 201:
            print(f"[e2e_v2] ✅ Rapport posté dans Issue #{GITHUB_ISSUE_NUMBER}")
            print(f"[e2e_v2] 🔗 https://github.com/{GITHUB_REPO}/issues/{GITHUB_ISSUE_NUMBER}")
            return True
        else:
            print(f"[e2e_v2] ❌ Erreur GitHub API : {response.status_code} — {response.text[:200]}")
            return False
    except Exception as e:
        print(f"[e2e_v2] ❌ Erreur réseau : {e}")
        return False


def executer_tests(module_name, priority_only=False, max_scenarios=0):
    print(f"\n[e2e_v2] ═══ PASSE 2 (execution reelle) — module '{module_name}' ═══\n")

    if not ODOO_PASSWORD:
        print("[e2e_v2] ⚠️  ODOO_PASSWORD non defini (variable d'environnement).")
        print("[e2e_v2] Definis-le avant de lancer, sinon Playwright ne pourra pas se connecter.")

    contrat, reponses = charger_contrat(module_name)
    if contrat is None:
        return

    # Charger les scenarios (passe 2 --generate-scenarios)
    scenarios_path = os.path.join(CONTRATS_DIR, f"{module_name}_scenarios.md")
    if not os.path.exists(scenarios_path):
        print(f"[e2e_v2] ❌ Scenarios introuvables : {scenarios_path}")
        print(f"[e2e_v2] Lance d'abord : python e2e_v2.py --generate-scenarios --module={module_name}")
        return
    with open(scenarios_path, encoding='utf-8') as f:
        scenarios = f.read()

    if priority_only:
        print("[e2e_v2] 🎯 Mode PRIORITAIRE : seulement test_level 1 + erreurs + transitions interdites + contraintes.")
    if max_scenarios:
        print(f"[e2e_v2] 🔒 Plafond : {max_scenarios} scenarios maximum.")

    print(f"[e2e_v2] Contrat + scenarios charges. Lancement de l'execution Playwright...")
    print(f"[e2e_v2] ⚠️  Cette etape va REELLEMENT interagir avec {ODOO_URL}")

    prompt = construire_prompt_run(module_name, contrat, scenarios, reponses,
                                   priority_only=priority_only,
                                   max_scenarios=max_scenarios)
    # Timeout large : l'execution reelle est longue
    reponse = appeler_claude(prompt, timeout=3600)

    if not reponse:
        print("[e2e_v2] ❌ Pas de rapport exploitable.")
        return

    # Sauvegarde du rapport
    os.makedirs(REPORTS_DIR, exist_ok=True)
    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    rapport_path = os.path.join(REPORTS_DIR, f"{module_name}_rapport_{now}.md")
    with open(rapport_path, "w", encoding="utf-8") as f:
        f.write(reponse)
    print(f"[e2e_v2] ✅ Rapport sauvegarde : {rapport_path}")

    # Poster le rapport dans l'issue GitHub (#5 par defaut)
    en_tete = (
        f"## 🧪 Rapport E2E v2 — {module_name} — "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    )
    poster_rapport_github(en_tete + reponse)

    print("\n" + "=" * 70)
    print("RAPPORT E2E :")
    print("=" * 70)
    print(reponse)
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    module = None
    analyze = False
    gen_scenarios = False
    run = False
    reuse = False   # --reuse-if-exists : reutilise le Contrat existant si present
    refresh_resume = False   # --refresh-resume : regenere le resume depuis le JSON
    priority_only = False
    max_scenarios = 0

    for arg in sys.argv[1:]:
        if arg == '--analyze':
            analyze = True
        elif arg == '--generate-scenarios':
            gen_scenarios = True
        elif arg == '--run':
            run = True
        elif arg == '--reuse-if-exists':
            reuse = True
        elif arg == '--refresh-resume':
            refresh_resume = True
        elif arg == '--priority-only':
            priority_only = True
        elif arg.startswith('--max-scenarios='):
            try:
                max_scenarios = int(arg.split('=', 1)[1].strip())
            except ValueError:
                max_scenarios = 0
        elif arg.startswith('--module='):
            module = arg.split('=', 1)[1].strip()

    if not module or not (analyze or gen_scenarios or run or refresh_resume):
        print("""
e2e_v2.py — E2E v2 (Contrat JSON + scenarios + execution)

Usage :
  # Passe 1 : generer le Contrat a partir du code
  python e2e_v2.py --analyze --module=hr_shoorah_demande

  # Passe 1 en mode economie : reutilise le Contrat existant s'il y en a un
  python e2e_v2.py --analyze --reuse-if-exists --module=hr_shoorah_demande

  # Passe 2a : generer les scenarios (sans executer) — pour valider le plan
  python e2e_v2.py --generate-scenarios --module=hr_shoorah_demande

  # Passe 2b : EXECUTER les scenarios sur Odoo via Playwright + rapport
  python e2e_v2.py --run --module=hr_shoorah_demande

  # Passe 2b limitee (gros modules) : seulement l'important, avec un plafond
  python e2e_v2.py --run --priority-only --max-scenarios=40 --module=hr_payroll_community

Options d'execution (--run) :
  --priority-only     ne teste que test_level 1 + erreurs + transitions interdites + contraintes
  --max-scenarios=N   plafond dur du nombre de scenarios (maitrise du cout)

Produit :
  contrats/<module>_contrat.json    (Contrat — passe 1)
  contrats/<module>_resume.md        (resume + questions — passe 1)
  contrats/<module>_scenarios.md     (plan de test — passe 2a)
  reports/<module>_rapport_*.md      (rapport final — passe 2b)
""".strip())
        sys.exit(0)

    if analyze:
        # force=True par defaut (regenere). --reuse-if-exists -> force=False
        analyser_module(module, force=not reuse)
    if refresh_resume:
        rafraichir_resume(module)
    if gen_scenarios:
        generer_scenarios(module)
    if run:
        executer_tests(module, priority_only=priority_only,
                        max_scenarios=max_scenarios)


if __name__ == '__main__':
    main()
