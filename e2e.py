# -*- coding: utf-8 -*-
"""
e2e.py — Orchestrateur E2E via Claude Code + MCP Playwright
=============================================================

Usage :
  python e2e.py --module=nom_module
  python e2e.py --all
  python e2e.py --list
"""

import subprocess
import sys
import os
import shutil
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION GLOBALE
# ══════════════════════════════════════════════════════════════════════════════

ROOT                = os.path.dirname(os.path.abspath(__file__))
GITHUB_REPO         = "mohammedaminedahmani-tech/extraplast_modules"
GITHUB_ISSUE_NUMBER = 3
ODOO_URL            = "https://daisy-consulting-extrat-plast7-test-33773518.dev.odoo.com/"
ODOO_EMAIL          = "im-it@daisyconsulting.ma"
ODOO_PASSWORD       = os.environ.get("ODOO_PASSWORD", "odoo")

# ══════════════════════════════════════════════════════════════════════════════
# MAPPING MODULES (auto-généré par apply_template.py)
# ══════════════════════════════════════════════════════════════════════════════

MODULES = {}


# ══════════════════════════════════════════════════════════════════════════════
# GITHUB — Poster le rapport dans l'Issue
# ══════════════════════════════════════════════════════════════════════════════

def poster_rapport_github(rapport: str):
    """Poste le rapport comme commentaire dans l'Issue GitHub."""

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
        print("[e2e] ⚠️  GITHUB_TOKEN manquant — rapport non posté sur GitHub")
        print("[e2e] Rapport local sauvegardé uniquement")
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
            print(f"[e2e] ✅ Rapport posté dans Issue #{GITHUB_ISSUE_NUMBER}")
            print(f"[e2e] 🔗 https://github.com/{GITHUB_REPO}/issues/{GITHUB_ISSUE_NUMBER}")
            return True
        else:
            print(f"[e2e] ❌ Erreur GitHub API : {response.status_code} — {response.text[:200]}")
            return False
    except Exception as e:
        print(f"[e2e] ❌ Erreur réseau : {e}")
        return False


# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE CODE — Tester un module via MCP Playwright
# ══════════════════════════════════════════════════════════════════════════════

def trouver_claude():
    return (
        shutil.which('claude.cmd')
        or shutil.which('claude')
        or os.path.join(os.environ.get('APPDATA', ''), 'npm', 'claude.cmd')
    )


def tester_module(module_name: str) -> str:
    """Lance Claude Code pour tester un module via MCP Playwright."""

    config = MODULES[module_name]
    context_path = config['context']

    full_context_path = os.path.join(ROOT, context_path)
    if not os.path.exists(full_context_path):
        msg = f"❌ **{module_name}** — CONTEXT.md manquant : `{context_path}`"
        print(f"[e2e] {msg}")
        return msg

    # Vérifier que le CONTEXT.md n'est pas vide
    with open(full_context_path, encoding='utf-8') as f:
        content = f.read().strip()
    if not content:
        msg = f"⚠️ **{module_name}** — CONTEXT.md vide — remplis-le avant de lancer les tests"
        print(f"[e2e] {msg}")
        return msg

    claude_exe = trouver_claude()
    if not claude_exe:
        print("[e2e] ❌ Claude Code CLI introuvable.")
        print("[e2e] Installez : npm i -g @anthropic-ai/claude-code")
        sys.exit(1)

    print(f"\n[e2e] 🧪 Test : {module_name}")
    print(f"[e2e] 📄 Context : {context_path}")
    print(f"[e2e] ⏳ Claude Code en cours...")

    prompt = f"""Lis {context_path}

Utilise MCP Playwright pour tester TOUS les scénarios de la section 'Scénarios à tester' sur :
URL : {ODOO_URL}
Login : {ODOO_EMAIL} / {ODOO_PASSWORD}

Pour chaque scénario :
✅ PASS si ça fonctionne comme décrit dans le CONTEXT.md
❌ FAIL + description exacte du bug si problème détecté

Retourne UNIQUEMENT un rapport markdown structuré comme ceci :

### {module_name}
| # | Scénario | Résultat | Détails |
|---|----------|----------|---------|
| 1 | ... | ✅ PASS | ... |
| 2 | ... | ❌ FAIL | ... |

**Total : X/Y PASS**

Ne crée aucun fichier. Retourne uniquement le rapport dans ta réponse."""

    try:
        proc = subprocess.Popen(
            [claude_exe, '-p', prompt, '--dangerously-skip-permissions', '--output-format', 'json'],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
        )

        print(f"[e2e] ⏳ En attente (peut prendre 5-15 minutes)...")
        stdout, stderr = proc.communicate(timeout=1800)

        if stdout:
            try:
                data = json.loads(stdout)
                if data.get('result'):
                    rapport = data['result'].strip()
                    print(f"[e2e] ✅ Test terminé — coût : ${data.get('total_cost_usd', 0):.4f}")
                    return rapport
                else:
                    return f"❌ **{module_name}** — Pas de résultat retourné par Claude"
            except json.JSONDecodeError:
                return f"❌ **{module_name}** — Erreur parsing réponse Claude"

        if stderr:
            print(f"[e2e] Erreur : {stderr[:200]}")

        return f"❌ **{module_name}** — Erreur lors du test"

    except subprocess.TimeoutExpired:
        proc.kill()
        return f"❌ **{module_name}** — Timeout (30 minutes dépassées)"
    except Exception as e:
        return f"❌ **{module_name}** — Exception : {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# RAPPORT — Assembler et poster
# ══════════════════════════════════════════════════════════════════════════════

def assembler_rapport(modules_testes: list, rapports: dict, label: str) -> str:
    """Assemble tous les rapports en un seul commentaire GitHub."""

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    lignes = [
        f"## 🧪 E2E Report — {label} — {now}",
        f"**Instance** : [{ODOO_URL}]({ODOO_URL})",
        f"**Modules testés** : {len(modules_testes)}",
        "",
    ]

    for module_name in modules_testes:
        rapport = rapports.get(module_name, f"❌ **{module_name}** — Non testé")
        lignes.append(rapport)
        lignes.append("")

    lignes.append("---")
    lignes.append("*Généré automatiquement par `e2e.py` + Claude Code + MCP Playwright*")

    return "\n".join(lignes)


def sauvegarder_rapport_local(rapport: str, label: str):
    """Sauvegarde le rapport localement dans reports/."""
    reports_dir = os.path.join(ROOT, 'reports')
    os.makedirs(reports_dir, exist_ok=True)

    now = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{label}_{now}.md"
    filepath = os.path.join(reports_dir, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(rapport)

    print(f"[e2e] 💾 Rapport local : reports/{filename}")
    return filepath


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    module  = None
    run_all = False

    for arg in sys.argv[1:]:
        if arg.startswith('--module='):
            module = arg.split('=', 1)[1].strip()
        elif arg == '--all':
            run_all = True
        elif arg == '--list':
            print("\nModules disponibles :\n")
            for m, cfg in MODULES.items():
                ctx = cfg['context']
                full = os.path.join(ROOT, ctx)
                if not os.path.exists(full):
                    statut = "❌ CONTEXT.md manquant"
                else:
                    with open(full, encoding='utf-8') as f:
                        statut = "✅ Prêt" if f.read().strip() else "⚠️  CONTEXT.md vide"
                print(f"  - {m} {statut}")
            print()
            sys.exit(0)

    if not any([module, run_all]):
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║        E2E Orchestrateur — Claude Code + MCP Playwright      ║
╚══════════════════════════════════════════════════════════════╝

Usage :
  python e2e.py --module=nom_module
  python e2e.py --all
  python e2e.py --list

Rapport posté automatiquement dans :
  https://github.com/{GITHUB_REPO}/issues/{GITHUB_ISSUE_NUMBER}
        """)
        sys.exit(0)

    # ── Construire la liste des modules à tester ─────────────────────────────
    if module:
        if module not in MODULES:
            print(f"[e2e] Module inconnu : '{module}'")
            print(f"[e2e] Lance : python e2e.py --list")
            sys.exit(1)
        modules_a_tester = [module]
        label = f"module_{module}"
    else:
        modules_a_tester = list(MODULES.keys())
        label = "tous_les_modules"

    # ── Tester chaque module ──────────────────────────────────────────────────
    print(f"\n[e2e] 🚀 Lancement — {label}")
    print(f"[e2e] Modules : {', '.join(modules_a_tester)}")
    print(f"[e2e] Rapport → Issue #{GITHUB_ISSUE_NUMBER}\n")

    rapports = {}
    for mod in modules_a_tester:
        rapports[mod] = tester_module(mod)

    # ── Assembler et poster le rapport ────────────────────────────────────────
    rapport_final = assembler_rapport(modules_a_tester, rapports, label)
    sauvegarder_rapport_local(rapport_final, label)
    poster_rapport_github(rapport_final)

    print(f"\n[e2e] ✅ Terminé — {len(modules_a_tester)} module(s) testés")


def post_last_report():
    """Poste le dernier rapport local dans GitHub sans relancer les tests."""
    import glob
    reports = sorted(glob.glob(os.path.join(ROOT, 'reports', '*.md')))
    if not reports:
        print("[e2e] ❌ Aucun rapport local trouvé dans reports/")
        return
    last = reports[-1]
    print(f"[e2e] 📄 Rapport trouvé : {os.path.basename(last)}")
    with open(last, encoding='utf-8') as f:
        rapport = f.read()
    poster_rapport_github(rapport)


if __name__ == '__main__':
    main()
