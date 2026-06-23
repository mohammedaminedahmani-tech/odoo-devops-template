# -*- coding: utf-8 -*-
"""
claude_review_v2.py
====================
Pre-commit hook Odoo — VERSION 2 (independante de claude_review.py).

Ce fichier est SEPARE de claude_review.py (version 1).
Un probleme dans ce fichier n'affecte PAS la version 1.

CE QUE FAIT CETTE VERSION :
  - Tout ce que fait claude_review.py (version 1) :
      * Lecture du cahier des charges
      * Detection des concepts Odoo dans chaque fichier
      * Interrogation ChromaDB (RAG documentation Odoo 19)
      * Analyse et verdict par Claude Code
      * Publication du rapport sur GitHub Issues
  - EN PLUS (nouveau dans cette version) :
      * Claude se connecte directement a la base Odoo via MCP Docker
      * Claude interroge lui-meme : modeles, champs+types, vues,
        menus, droits d'acces, contraintes SQL, groupes de securite
      * Detection de conflits entre le code commite et la base reelle

UTILISATION :
  Appeler via .pre-commit-config-v2.yaml uniquement.
  La version 1 (.pre-commit-config.yaml + claude_review.py) reste intacte.

OUTILS MCP disponibles pour Claude :
  list_models, get_model_fields, search_records, diagnose_access,
  schema_catalog, get_odoo_profile, scan_addons_source

CORRECTIONS v2.1 :
  - Fix #1 : regex _sql_constraints trop large -> assignation de classe uniquement
  - Fix #2 : ChromaDB embedding -> SentenceTransformerEmbeddingFunction
  - Fix #3 : SSL SaaS Odoo -> desactivation verification SSL (dev uniquement)
"""

import subprocess
import sys
import os
import re
import json
import ssl
import urllib.request
import urllib.error
from datetime import datetime
import shutil
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# ── FIX #3 : Desactivation SSL pour SaaS Odoo (dev uniquement) ───────────────
# Le certificat dev.odoo.com ne couvre pas les sous-domaines custom.
# A RETIRER en production si le certificat est valide.
ssl._create_default_https_context = ssl._create_unverified_context

# ── CORRECTION ENCODAGE WINDOWS (cp1252) ──────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = open(sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1)
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = open(sys.stderr.fileno(), mode="w", encoding="utf-8", buffering=1)

import chromadb
# ── FIX #2 : Utilisation de SentenceTransformerEmbeddingFunction ─────────────
# HuggingFaceEmbeddings (LangChain) n'implemente pas l'interface ChromaDB.
# SentenceTransformerEmbeddingFunction est compatible nativement.
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = "mohammedaminedahmani-tech/extraplast_modules"
GITHUB_ISSUE_NUM = 1
EMAIL_ONLY_ERRORS = False

EXTENSIONS_CIBLES = {".py", ".xml", ".js", ".csv", ".json"}
MAX_TAILLE_FICHIER = 150000  # 150 KB

MOT_CLE_OK = "COMMIT_OK"
MOT_CLE_ERREUR = "COMMIT_ERREUR"

FICHIER_PROJET = "SETUP.md"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odoo_global_db")

# ── Configuration MCP Odoo Docker ─────────────────────────────────────────────
ODOO_MCP_IMAGE = os.environ.get("ODOO_MCP_IMAGE", "mcp/odoo")
ODOO_URL_INTERNE = os.environ.get(
    "ODOO_URL",
    "https://daisy-consulting-extrat-plast7-test-33133732.dev.odoo.com"
)
ODOO_DB = os.environ.get("ODOO_DB", "daisy-consulting-extrat-plast7-test-33133732")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME", "im-it@daisyconsulting.ma")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "odoo")
ODOO_ENABLE_WRITES = os.environ.get("ODOO_MCP_ENABLE_WRITES", "0")
ODOO_ADDONS_PATH = os.environ.get("ODOO_ADDONS_PATH", "")

# ══════════════════════════════════════════════════════════════════════════════
# DETECTION DES ELEMENTS ODOO
# ══════════════════════════════════════════════════════════════════════════════

PATTERNS_ODOO = {
    "py": [
        (r"class\s+\w+\s*\(.*models\.(Model|TransientModel|AbstractModel)",
         "Odoo ORM model definition"),
        (r"fields\.(Char|Integer|Float|Boolean|Many2one|One2many|Many2many"
         r"|Selection|Date|Datetime|Binary|Html|Text|Monetary)",
         "Odoo field types"),
        (r"@api\.(depends|onchange|constrains|model|model_create_multi|returns)",
         "Odoo API decorators"),
        (r"(mail\.thread|mail\.activity\.mixin)", "Odoo mail thread mixin"),
        (r"_inherit\s*=", "Odoo model inheritance"),
        (r"^\s+_sql_constraints\s*=", "Odoo SQL constraints"),
        (r"wizard|TransientModel", "Odoo wizard TransientModel"),
        (r"security|ir\.rule|res\.groups", "Odoo security rules"),
        (r"(action_|view_id|res_model|view_mode)", "Odoo action window"),
        (r"cron|ir\.cron", "Odoo scheduled actions cron"),
    ],
    "xml": [
        (r"<record model=\"ir\.ui\.view\"", "Odoo view definition XML"),
        (r"<record model=\"ir\.actions", "Odoo action definition XML"),
        (r"<record model=\"ir\.model\.access\"", "Odoo access rights XML"),
        (r"<menuitem", "Odoo menu item XML"),
        (r"<field name=\"arch\"", "Odoo view arch XML"),
        (r"(form|tree|kanban|list|search|pivot|graph|calendar)", "Odoo view types"),
        (r"<xpath", "Odoo XML xpath inheritance"),
        (r"<data noupdate", "Odoo data noupdate XML"),
    ],
    "js": [
        (r"owl|Component|useState|onWillStart", "Odoo OWL framework component"),
        (r"registry\.category", "Odoo JS registry"),
        (r"useService|useBus", "Odoo OWL hooks"),
        (r"rpc|jsonrpc|fetch.*web/dataset", "Odoo RPC call"),
    ],
}


def extraire_concepts_odoo(contenu, extension):
    ext = extension.lstrip(".")
    patterns = PATTERNS_ODOO.get(ext, [])
    concepts = []
    for pattern, description in patterns:
        if re.search(pattern, contenu, re.IGNORECASE | re.MULTILINE):
            concepts.append(description)
    return list(set(concepts))


def extraire_noms_modeles(contenu):
    elements = []
    for m in re.finditer(r'(?<!\w)_name\s*=\s*[\'"]([^\'"]+)[\'"]', contenu):
        elements.append(("_name", m.group(1)))
    for m in re.finditer(r'_inherit\s*=\s*[\'"]([^\'"]+)[\'"]', contenu):
        elements.append(("_inherit", m.group(1)))
    for m in re.finditer(r'_inherit\s*=\s*\[([^\]]+)\]', contenu):
        for n in re.finditer(r'[\'"]([^\'"]+)[\'"]', m.group(1)):
            elements.append(("_inherit_list", n.group(1)))
    return elements


def extraire_champs_py(contenu):
    champs = []
    for m in re.finditer(r'(\w+)\s*=\s*fields\.(\w+)\s*\(', contenu):
        champs.append({"nom": m.group(1), "type": m.group(2)})
    return champs


def extraire_external_ids_xml(contenu):
    ids = []
    for m in re.finditer(r'<record[^>]+id=[\'"]([^\'"]+)[\'"]', contenu):
        ids.append(m.group(1))
    for m in re.finditer(r'<menuitem[^>]+id=[\'"]([^\'"]+)[\'"]', contenu):
        ids.append(m.group(1))
    return list(set(ids))


# ══════════════════════════════════════════════════════════════════════════════
# CHROMADB — RAG Documentation Odoo 19
# ══════════════════════════════════════════════════════════════════════════════

_chroma_collection = None


def get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        print("[claude_review_v2] [DB] Connexion a la base ChromaDB...")
        # FIX #2 : SentenceTransformerEmbeddingFunction compatible ChromaDB
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        client = chromadb.PersistentClient(path=DB_PATH)
        _chroma_collection = client.get_collection(
            name="odoo_global_docs",
            embedding_function=ef
        )
        print(
            f"[claude_review_v2] [DB] Base connectee "
            f"({_chroma_collection.count()} documents)"
        )
    return _chroma_collection


def interroger_base_odoo(concepts, nom_fichier, n_results=4):
    if not concepts:
        return "Aucun element Odoo specifique detecte dans ce fichier."
    query = f"Odoo 19 {' '.join(concepts)} best practices rules {nom_fichier}"
    print(f"[claude_review_v2] [DB] Query pour {nom_fichier} : {concepts}")
    try:
        collection = get_collection()
        results = collection.query(query_texts=[query], n_results=n_results)
        if not results['documents'] or not results['documents'][0]:
            return "Aucune documentation pertinente trouvee pour ce fichier."
        doc_extraite = ""
        for i, doc in enumerate(results['documents'][0]):
            doc_extraite += f"[Doc {i+1}] :\n{doc}\n---\n"
        return doc_extraite
    except Exception as e:
        sys.stderr.write(f"[claude_review_v2] [ERREUR] DB inaccessible : {e}\n")
        return "Base de donnees inaccessible."


# ══════════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DES BLOCS RAG + HINTS MCP
# ══════════════════════════════════════════════════════════════════════════════

def construire_blocs_rag(fichiers):
    """
    Pour chaque fichier :
      1. Lit le contenu
      2. Detecte les concepts Odoo
      3. Interroge ChromaDB (RAG)
      4. Genere les hints MCP pour guider Claude
      5. Retourne un bloc enrichi fichier + doc + hints MCP
    """
    blocs = []

    for chemin in fichiers:
        extension = os.path.splitext(chemin)[1]
        nom_fichier = os.path.basename(chemin)
        ext = extension.lstrip(".")

        print(f"\n[claude_review_v2] [ANALYSE] Traitement de : {chemin}")

        # 1. Lecture du fichier
        try:
            with open(chemin, encoding="utf-8", errors="replace") as fh:
                contenu = fh.read(MAX_TAILLE_FICHIER)
        except FileNotFoundError:
            contenu = "[Fichier introuvable]"

        # 2. Detection des concepts Odoo
        concepts = extraire_concepts_odoo(contenu, extension)
        if concepts:
            print(f"[claude_review_v2] [DETECT] Concepts trouves : {concepts}")
        else:
            print(
                f"[claude_review_v2] [DETECT] "
                f"Pas de pattern Odoo specifique dans {nom_fichier}"
            )

        # 3. Interrogation ChromaDB
        doc_pertinente = interroger_base_odoo(concepts, nom_fichier)

        # 4. Generation des hints MCP
        hints_mcp = []

        if ext == "py":
            modeles = extraire_noms_modeles(contenu)
            champs = extraire_champs_py(contenu)

            for type_m, nom_m in modeles:
                if type_m == "_name":
                    hints_mcp.append(
                        f"- Verifier si le modele `{nom_m}` existe deja en base : "
                        f"list_models(query='{nom_m}')"
                    )
                    hints_mcp.append(
                        f"- Si `{nom_m}` existe, recuperer ses champs actuels : "
                        f"get_model_fields(model='{nom_m}')"
                    )
                elif type_m in ("_inherit", "_inherit_list"):
                    hints_mcp.append(
                        f"- CRITIQUE : verifier que le modele herite `{nom_m}` EXISTE : "
                        f"list_models(query='{nom_m}')"
                    )

            if champs:
                hints_mcp.append(
                    "- Champs definis dans ce fichier : "
                    + ", ".join(f"`{c['nom']}` ({c['type']})" for c in champs[:10])
                )
                hints_mcp.append(
                    "- Pour chaque champ, comparer son type avec celui en base "
                    "via get_model_fields et detecter les conflits de type"
                )

            # FIX #1 : regex plus precise — uniquement les vraies assignations
            # de classe _sql_constraints, pas les occurrences dans les strings/comments
            if re.search(r'^\s+_sql_constraints\s*=', contenu, re.MULTILINE):
                for m in re.finditer(
                    r'_sql_constraints\s*=\s*\[.*?\(\s*[\'"]([^\'"]+)[\'"]',
                    contenu, re.DOTALL
                ):
                    hints_mcp.append(
                        f"- Verifier la contrainte SQL `{m.group(1)}` : "
                        f"search_records(model='ir.model.constraint', "
                        f"domain=[['name','=','{m.group(1)}']])"
                    )

        elif ext == "xml":
            ids = extraire_external_ids_xml(contenu)
            for xid in ids[:8]:
                hints_mcp.append(
                    f"- Verifier si l'ID XML `{xid}` existe deja en base : "
                    f"search_records(model='ir.ui.view', "
                    f"domain=[['key','like','{xid}']])"
                )

            for m in re.finditer(
                r'inherit_id[^>]*ref=[\'"]([^\'"]+)[\'"]', contenu
            ):
                ref = m.group(1)
                hints_mcp.append(
                    f"- CRITIQUE : verifier que la vue parente `{ref}` existe : "
                    f"search_records(model='ir.ui.view', "
                    f"domain=[['key','=','{ref}']])"
                )

            for m in re.finditer(
                r'<field name=[\'"]res_model[\'"]>([^<]+)<', contenu
            ):
                mod = m.group(1).strip()
                hints_mcp.append(
                    f"- Verifier que le modele d'action `{mod}` existe : "
                    f"list_models(query='{mod}')"
                )

            for m in re.finditer(
                r'<menuitem[^>]+name=[\'"]([^\'"]+)[\'"]', contenu
            ):
                hints_mcp.append(
                    f"- Verifier le menu `{m.group(1)}` : "
                    f"search_records(model='ir.ui.menu', "
                    f"domain=[['name','=','{m.group(1)}']])"
                )

        elif ext == "csv":
            if "access" in chemin.lower():
                hints_mcp.append(
                    "- Fichier de droits d'acces : "
                    "verifier via search_records(model='ir.model.access') "
                    "et diagnose_access pour chaque modele reference"
                )

        # 5. Construction du bloc enrichi
        bloc = f"""
=== FICHIER : {chemin} ===

-- CONCEPTS ODOO DETECTES --
{', '.join(concepts) if concepts else 'Aucun pattern Odoo specifique'}

-- VERIFICATIONS A FAIRE VIA OUTILS MCP ODOO (OBLIGATOIRES) --
{chr(10).join(hints_mcp) if hints_mcp else '- Analyser generalement le fichier par rapport au projet et a la base Odoo'}

-- DOCUMENTATION OFFICIELLE ODOO 19 PERTINENTE POUR CE FICHIER --
{doc_pertinente}

-- CONTENU DU FICHIER --
```{ext}
{contenu}
```
""".strip()

        blocs.append(bloc)

    return "\n\n" + ("=" * 60) + "\n\n".join(blocs)


# ══════════════════════════════════════════════════════════════════════════════
# MCP — Generation config Docker
# ══════════════════════════════════════════════════════════════════════════════

def generer_mcp_config():
    """
    Genere un fichier mcp_config.json temporaire pour Claude Code.
    Supprime automatiquement apres utilisation.
    """
    docker_args = [
    "run", "-i", "--rm",
    "-e", f"ODOO_URL={ODOO_URL_INTERNE}",
    "-e", f"ODOO_DB={ODOO_DB}",
    "-e", f"ODOO_USERNAME={ODOO_USERNAME}",
    "-e", f"ODOO_PASSWORD={ODOO_PASSWORD}",
    "-e", f"ODOO_MCP_ENABLE_WRITES={ODOO_ENABLE_WRITES}",
    "-e", "ODOO_SSL_VERIFY=false",
]

    if ODOO_ADDONS_PATH and os.path.isdir(ODOO_ADDONS_PATH):
        abs_path = os.path.abspath(ODOO_ADDONS_PATH)
        docker_args += [
            "-v", f"{abs_path}:/mnt/addons:ro",
            "-e", "ODOO_ADDONS_PATHS=/mnt/addons",
        ]
        print(f"[claude_review_v2] [MCP] Addons montes : {abs_path}")

    docker_args.append(ODOO_MCP_IMAGE)

    config = {"mcpServers": {"odoo": {"command": "docker", "args": docker_args}}}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "_mcp_config_tmp.json")

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"[claude_review_v2] [MCP] Config MCP generee -> {config_path}")
    return config_path


# ══════════════════════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

PROMPT_COMPREHENSION = """
Tu es un Architecte Logiciel Senior expert en Odoo 19 et le Gardien de ce projet.

AVANT TOUTE ANALYSE, lis attentivement le cahier des charges ci-dessous et confirme
ta comprehension en repondant UNIQUEMENT avec un resume structure de ce format :

PROJET_COMPRIS:
- Module 1 : <nom> | But : <but en 1 ligne> | Roles : <roles> | Flux : <flux principal>
- Module 2 : <nom> | But : <but en 1 ligne> | Roles : <roles> | Flux : <flux principal>
- Regles metier cles : <liste des 3-5 regles les plus importantes>
- Modeles Odoo attendus : <liste des modeles probables>

--- CAHIER DES CHARGES ({nom_fichier_projet}) ---
{contexte_projet}
--- FIN CAHIER DES CHARGES ---
""".strip()

PROMPT_ANALYSE = """
Tu es un Architecte Logiciel Senior expert en Odoo 19 et le Gardien de ce projet.
Tu as acces a une instance Odoo REELLE via les outils MCP `odoo`.

╔═══════════════════════════════════════════════════════════════════╗
║  REGLES ABSOLUES                                                  ║
║  1. Tu DOIS utiliser les outils MCP avant de rendre ton verdict  ║
║  2. Commence par get_odoo_profile (version + modules installes)   ║
║  3. Pour CHAQUE element detecte : verifie en base Odoo via MCP   ║
║  4. Ne suppose rien sur la base : interroge-la avec les outils   ║
╚═══════════════════════════════════════════════════════════════════╝

== ETAPE 1 : CONTEXTE PROJET (LIS ET APPLIQUE STRICTEMENT) ==
{contexte_projet}

== ETAPE 2 : ANALYSE FICHIER PAR FICHIER AVEC DOC ODOO 19 + MCP ==
Chaque fichier ci-dessous est accompagne de :
  - Les concepts Odoo detectes dans ce fichier
  - Les verifications MCP OBLIGATOIRES a effectuer sur la base Odoo
  - La documentation officielle Odoo 19 PERTINENTE (RAG)
  - Le contenu complet du fichier

Pour chaque fichier, tu dois :
  a) Executer les verifications MCP listees dans son bloc
  b) Comprendre ce que fait le code
  c) Verifier par rapport a la doc Odoo 19 fournie
  d) Verifier par rapport au cahier des charges du projet
  e) Identifier tout conflit avec la base Odoo ou ecart projet

{blocs_rag}

== ETAPE 3 : OUTILS MCP SUPPLEMENTAIRES DISPONIBLES ==
En plus des hints par fichier, tu peux aussi utiliser :
  - schema_catalog(query='<terme>') pour chercher des modeles similaires
  - diagnose_access(model='<modele>') pour les droits d'acces complets
  - search_records(model='ir.model.constraint', domain=[['name','=','<nom>']])
  - get_odoo_profile() pour la version Odoo et les modules installes

== ETAPE 4 : FORMAT DE REPONSE OBLIGATOIRE ==

Ta reponse doit etre separee en DEUX parties par le mot-cle ---DETAIL--- :

PARTIE 1 (avant ---DETAIL---) : verdict global sur UNE seule ligne :
  - COMMIT_OK
  - COMMIT_ERREUR: <resume du probleme bloquant principal>

PARTIE 2 (apres ---DETAIL---) : rapport Markdown complet :

## Verifications MCP effectuees
(Liste precisement les appels MCP que tu as faits et leurs resultats)

## Comprehension du projet appliquee
(Montre que tu as compris le projet et comment le code s'y rattache)

## Analyse par fichier

Pour CHAQUE fichier, utilise ce format exact :

### [FICHIER_OK] ou [FICHIER_ERREUR] : nom_du_fichier
**Verdict** : OK / ERREUR BLOQUANTE / AVERTISSEMENT
**Concepts Odoo** : (ce que tu as analyse)
**Verifications MCP** : (resultats des outils MCP pour ce fichier)
**Conflits avec la base** : (ecarts entre le code et l'etat reel Odoo)
**Points corrects** : (ce qui respecte le projet et Odoo 19)
**Avertissements** : (non bloquants)
**Erreurs bloquantes** : (ecarts graves)
**Correctif propose** : (code ou explication concrete)

---

## Verdict global

| Fichier | Statut | Probleme principal |
|---|---|---|
| nom_fichier | OK / ERREUR / AVERT | description |

**Decision finale** : COMMIT_OK / COMMIT_ERREUR
**Raison** : (resume en 1-2 phrases)
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# APPEL CLAUDE CODE CLI
# ══════════════════════════════════════════════════════════════════════════════

def appeler_claude(prompt, mcp_config_path=None, timeout=300):
    """
    Lance Claude Code CLI en mode non-interactif.
    Avec mcp_config_path : Claude a acces aux outils MCP Odoo.
    --strict-mcp-config : Claude utilise UNIQUEMENT ce MCP.
    --dangerously-skip-permissions : requis en mode headless (pre-commit).
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(script_dir, "_prompt_tmp_v2.txt")

    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    # Resolve claude executable (Windows: subprocess ne trouve pas .ps1)
    claude_exe = (
        shutil.which("claude.cmd")
        or shutil.which("claude")
        or os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")
    )
    if not claude_exe or not os.path.exists(claude_exe):
        sys.stderr.write(
            "[claude_review_v2] claude CLI introuvable. "
            "Installez Claude Code (npm i -g @anthropic-ai/claude-code) "
            "ou ajoutez %APPDATA%\\npm au PATH.\n"
        )
        sys.exit(2)

    cmd = [claude_exe, "-p", "@" + prompt_file]

    if mcp_config_path:
        cmd += [
            "--mcp-config", mcp_config_path,
            "--strict-mcp-config",
            "--dangerously-skip-permissions",
        ]

    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"[claude_review_v2] TIMEOUT apres {timeout}s\n")
        sys.exit(2)
    finally:
        if os.path.exists(prompt_file):
            os.remove(prompt_file)

    if r.returncode != 0:
        sys.stderr.write(
            f"[claude_review_v2] Erreur Claude CLI (code {r.returncode}):\n"
            f"STDERR: {r.stderr[:500]}\n"
        )
        sys.exit(2)

    return r.stdout.strip()


# ══════════════════════════════════════════════════════════════════════════════
# GIT & FICHIERS
# ══════════════════════════════════════════════════════════════════════════════

def get_fichiers_modifies():
    """Mode normal — seulement les fichiers stages (git add)"""
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if r.returncode != 0:
        sys.stderr.write("[claude_review_v2] Erreur git : " + r.stderr + "\n")
        sys.exit(1)
    return [f.strip() for f in r.stdout.splitlines() if f.strip()]


def get_tous_fichiers():
    """Mode audit global — tous les fichiers du projet sans exception"""
    racine = os.path.dirname(os.path.abspath(__file__))
    fichiers = []
    DOSSIERS_EXCLUS = {
        '.git', '__pycache__', 'node_modules',
        'odoo_global_db', 'mcp-odoo', '.vscode',
        'tests', 'playwright-report', 'static',
        'report', '.github'
    }
    FICHIERS_EXCLUS = {
        'claude_review_v2.py', 'claude_review.py',
        'claude_e2e_generator.py', 'bypass_commit.py',
        'playwright.config.js', '_mcp_config_tmp.json'
    }
    for root, dirs, files in os.walk(racine):
        dirs[:] = [d for d in dirs
                   if d not in DOSSIERS_EXCLUS
                   and not d.startswith('.')]
        for f in files:
            if f not in FICHIERS_EXCLUS:
                chemin = os.path.relpath(
                    os.path.join(root, f), racine)
                fichiers.append(chemin)
    return fichiers

def get_fichiers_module(nom_module):
    """
    Mode module précis :
    - Trouve le dossier du module par son nom
    - Collecte tous ses fichiers (.py, .xml, .js, .csv, .json)
    - Lit __manifest__.py pour trouver les dépendances
    - Ajoute les fichiers des dépendances custom (pas les modules Odoo standard)
    """
    racine = os.path.dirname(os.path.abspath(__file__))

    # Modules Odoo standard à ignorer
    MODULES_STANDARD = {
        'base', 'mail', 'account', 'stock', 'sale', 'purchase',
        'hr', 'project', 'mrp', 'product', 'uom', 'web', 'board',
        'sale_management', 'purchase_stock', 'account_accountant',
        'stock_account', 'hr_expense', 'analytic', 'digest',
    }

    def collecter_fichiers_dossier(dossier):
        """Collecte tous les fichiers cibles dans un dossier."""
        fichiers = []
        DOSSIERS_EXCLUS = {'__pycache__', 'static', 'tests', 'node_modules'}
        for root, dirs, files in os.walk(dossier):
            dirs[:] = [d for d in dirs if d not in DOSSIERS_EXCLUS]
            for f in files:
                if os.path.splitext(f)[1] in EXTENSIONS_CIBLES:
                    chemin = os.path.relpath(os.path.join(root, f), racine)
                    fichiers.append(chemin)
        return fichiers

    def trouver_module(nom):
        """Cherche un module par son nom dans tout le projet."""
        for root, dirs, files in os.walk(racine):
            if (os.path.basename(root) == nom
                    and '__manifest__.py' in files):
                return root
        return None

    def lire_depends(module_path):
        """Lit les dépendances depuis __manifest__.py."""
        manifest_path = os.path.join(module_path, '__manifest__.py')
        try:
            with open(manifest_path, encoding='utf-8') as f:
                content = f.read()
            m = re.search(
                r"['\"]depends['\"]\s*:\s*\[([^\]]+)\]",
                content, re.DOTALL
            )
            if m:
                return re.findall(r"['\"]([^'\"]+)['\"]", m.group(1))
        except Exception as e:
            sys.stderr.write(f"[claude_review_v2] Erreur manifest : {e}\n")
        return []

    # ── Trouver le module principal ──────────────────────────────────────────
    module_path = trouver_module(nom_module)
    if not module_path:
        sys.stderr.write(
            f"[claude_review_v2] ERREUR : Module '{nom_module}' "
            f"introuvable dans le projet.\n"
        )
        sys.exit(1)

    print(f"[claude_review_v2] Module trouvé : {module_path}")

    # ── Collecter fichiers du module principal ───────────────────────────────
    fichiers = collecter_fichiers_dossier(module_path)
    print(f"[claude_review_v2] Fichiers module principal ({nom_module}) : "
          f"{len(fichiers)}")

    # ── Lire et résoudre les dépendances ────────────────────────────────────
    depends = lire_depends(module_path)
    print(f"[claude_review_v2] Dépendances déclarées : {depends}")

    modules_visites = {nom_module}

    def resoudre_depends(deps):
        """Résolution récursive des dépendances custom."""
        for dep in deps:
            if dep in modules_visites or dep in MODULES_STANDARD:
                continue
            modules_visites.add(dep)

            dep_path = trouver_module(dep)
            if dep_path:
                dep_fichiers = collecter_fichiers_dossier(dep_path)
                nouveaux = [f for f in dep_fichiers if f not in fichiers]
                fichiers.extend(nouveaux)
                print(
                    f"[claude_review_v2] Dépendance custom '{dep}' : "
                    f"+{len(nouveaux)} fichiers"
                )
                # Récursif — dépendances des dépendances
                sous_depends = lire_depends(dep_path)
                resoudre_depends(sous_depends)
            else:
                print(
                    f"[claude_review_v2] Dépendance '{dep}' : "
                    f"module Odoo standard, ignoré"
                )

    resoudre_depends(depends)

    print(f"[claude_review_v2] Total fichiers à analyser : {len(fichiers)}")
    return fichiers

    

def get_git_info():
    def run(cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else "inconnu"
    return {
        "branch": run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "author": run(["git", "config", "user.name"]),
        "email": run(["git", "config", "user.email"]),
        "message": run(["git", "log", "-1", "--format=%s"]),
    }


def filtrer(fichiers):
    return [f for f in fichiers if os.path.splitext(f)[1] in EXTENSIONS_CIBLES]


# ══════════════════════════════════════════════════════════════════════════════
# GITHUB
# ══════════════════════════════════════════════════════════════════════════════

def poster_commentaire_github(corps_markdown):
    if not GITHUB_TOKEN:
        sys.stderr.write("[claude_review_v2] [INFO] GITHUB_TOKEN non defini.\n")
        return
    url = (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/issues/{GITHUB_ISSUE_NUM}/comments"
    )
    data = json.dumps({"body": corps_markdown}).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": "Bearer " + GITHUB_TOKEN,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        }, method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            print(
                f"[claude_review_v2] Rapport poste sur "
                f"GitHub Issue #{GITHUB_ISSUE_NUM}"
            )
    except urllib.error.HTTPError as e:
        sys.stderr.write(f"[claude_review_v2] GitHub erreur : {e}\n")


def construire_corps(statut_ok, reponse_detail, fichiers, git_info):
    tag = "OK" if statut_ok else "KO"
    statut_txt = "ACCEPTE" if statut_ok else "REFUSE"
    liste_fich = "\n".join(f"- `{f}`" for f in fichiers)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return (
        f"## [{tag}] Audit RAG + MCP Odoo Live — Commit {statut_txt}\n"
        f"*Analyse v2 : {now}*\n\n"
        f"| Auteur | Branche | Message |\n|---|---|---|\n"
        f"| {git_info['author']} | `{git_info['branch']}` "
        f"| {git_info['message']} |\n\n"
        f"### Connexion Odoo (MCP)\n"
        f"| Image MCP | Base | URL |\n|---|---|---|\n"
        f"| `{ODOO_MCP_IMAGE}` | `{ODOO_DB}` | `{ODOO_URL_INTERNE}` |\n\n"
        f"### Fichiers analyses ({len(fichiers)})\n{liste_fich}\n\n"
        f"---\n\n"
        f"{reponse_detail}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    sep = "=" * 70
    print(sep)
    print("[claude_review_v2] VERSION 2.1 : Analyse RAG + MCP Odoo Live")
    print(f"[claude_review_v2] Odoo : {ODOO_URL_INTERNE} | DB : {ODOO_DB}")
    print(sep)

    tous = get_fichiers_modifies()
    cibles = filtrer(tous)

    if not cibles:
        print("[claude_review_v2] Aucun fichier pertinent. Commit autorise.")
        sys.exit(0)

    print(f"[claude_review_v2] {len(cibles)} fichier(s) a analyser : {cibles}")
    git_info = get_git_info()

    # ── ETAPE 1 : Cahier des charges ─────────────────────────────────────────
    print(f"\n[claude_review_v2] [ETAPE 1] Lecture du cahier des charges...")
    try:
        with open(FICHIER_PROJET, encoding="utf-8", errors="replace") as fh:
            contexte_projet = fh.read()
        print(f"[claude_review_v2] -> OK ({len(contexte_projet)} caracteres)")
    except FileNotFoundError:
        contexte_projet = "[AVERTISSEMENT : Fichier projet introuvable]"

    # ── ETAPE 2 : Comprehension projet (sans MCP, rapide) ────────────────────
    print("\n[claude_review_v2] [ETAPE 2] Comprehension du projet...")
    comprehension = appeler_claude(
        PROMPT_COMPREHENSION.format(
            nom_fichier_projet=FICHIER_PROJET,
            contexte_projet=contexte_projet,
        ),
        mcp_config_path=None,
        timeout=300,
    )
    print(f"\n[claude_review_v2] Comprehension :\n{comprehension}\n")

    # ── ETAPE 3 : Blocs fichiers + RAG + hints MCP ───────────────────────────
    print("\n[claude_review_v2] [ETAPE 3] Analyse fichiers + RAG ChromaDB...")
    blocs_rag = construire_blocs_rag(cibles)

    # ── ETAPE 4 : Generation config MCP ──────────────────────────────────────
    print("\n[claude_review_v2] [ETAPE 4] Generation config MCP Odoo Docker...")
    mcp_config_path = generer_mcp_config()

    # ── ETAPE 5 : Analyse Claude Code + MCP Odoo ─────────────────────────────
    print("\n[claude_review_v2] [ETAPE 5] Claude analyse avec acces MCP Odoo...")
    print("[claude_review_v2] -> Claude va interroger directement la base Odoo")

    prompt_analyse = PROMPT_ANALYSE.format(
        contexte_projet=contexte_projet,
        blocs_rag=blocs_rag,
    )

    reponse_brute = appeler_claude(
        prompt_analyse,
        mcp_config_path=mcp_config_path,
        timeout=1800,
    )

    # Nettoyage config MCP temporaire
    if os.path.exists(mcp_config_path):
        os.remove(mcp_config_path)

    # ── Parsing du verdict ────────────────────────────────────────────────────
    if "---DETAIL---" in reponse_brute:
        parties = reponse_brute.split("---DETAIL---", 1)
        ligne_decision = parties[0].strip()
        detail_markdown = parties[1].strip()
    else:
        lignes = reponse_brute.split("\n")
        ligne_decision = lignes[0].strip()
        detail_markdown = reponse_brute

    print(f"\n{sep}")
    print(f"[claude_review_v2] DECISION : {ligne_decision}")
    print(sep)

    statut_ok = MOT_CLE_OK in ligne_decision
    statut_erreur = MOT_CLE_ERREUR in ligne_decision

    if not EMAIL_ONLY_ERRORS or statut_erreur:
        poster_commentaire_github(
            construire_corps(statut_ok, detail_markdown, cibles, git_info)
        )

    if statut_ok:
        print("[claude_review_v2] COMMIT AUTORISE")
        sys.exit(0)
    elif statut_erreur:
        print("[claude_review_v2] COMMIT BLOQUE — Corriger les erreurs avant de recommiter")
        sys.exit(1)
    else:
        print("[claude_review_v2] Verdict ambigu — Commit autorise par defaut")
        sys.exit(0)


if __name__ == "__main__":
    main()
