# -*- coding: utf-8 -*-
"""
apply_template.py
=================
Script d'installation automatique du template Odoo DevOps.

Usage :
  python apply_template.py
"""

import os
import sys
import shutil

# ══════════════════════════════════════════════════════════════════════════════
# FICHIERS A COPIER
# ══════════════════════════════════════════════════════════════════════════════

FICHIERS = [
    "claude_review_v2.py",
    ".pre-commit-config-v2.yaml",
    "e2e.py",
    "requirements.txt",
    "projet.md",
    "SETUP.md",
    ".env.example",
]

DOSSIERS = [
    ".github",
    "mcp-odoo",
]

# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("   Odoo DevOps Template — Installation automatique")
    print("=" * 60)

    # ── 1. Chemin du projet cible ─────────────────────────────────────────
    target = input("\n📁 Chemin vers ton projet Odoo ? ").strip().strip('"')
    if not os.path.isdir(target):
        print(f"❌ Dossier introuvable : {target}")
        sys.exit(1)

    # ── 2. Infos projet ───────────────────────────────────────────────────
    print("\n📋 Configuration du projet :")
    github_repo = input("   GitHub Repo (ex: org/mon-projet) ? ").strip()
    odoo_url    = input("   URL Odoo (ex: https://mon-instance.dev.odoo.com) ? ").strip()
    odoo_db     = input("   DB Odoo ? ").strip()
    odoo_user   = input("   Username Odoo ? ").strip()
    odoo_pass   = input("   Password Odoo ? ").strip()
    odoo_ver    = input("   Version Odoo (17/18/19) ? ").strip()

    # ── 3. Copie des fichiers ─────────────────────────────────────────────
    print("\n📦 Copie des fichiers...")
    template_dir = os.path.dirname(os.path.abspath(__file__))

    for fichier in FICHIERS:
        src = os.path.join(template_dir, fichier)
        dst = os.path.join(target, fichier)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"   ✅ {fichier}")
        else:
            print(f"   ⚠️  {fichier} introuvable dans le template")

    for dossier in DOSSIERS:
        src = os.path.join(template_dir, dossier)
        dst = os.path.join(target, dossier)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"   ✅ {dossier}/")
        else:
            print(f"   ⚠️  {dossier}/ introuvable dans le template")

    # ── 4. Configuration claude_review_v2.py ─────────────────────────────
    print("\n⚙️  Configuration claude_review_v2.py...")
    review_path = os.path.join(target, "claude_review_v2.py")
    if os.path.exists(review_path):
        with open(review_path, encoding="utf-8") as f:
            content = f.read()

        content = content.replace(
            'GITHUB_REPO = "mohammedaminedahmani-tech/extraplast_modules"',
            f'GITHUB_REPO = "{github_repo}"'
        )
        content = content.replace(
            '"https://daisy-consulting-extrat-plast7-test-33133732.dev.odoo.com"',
            f'"{odoo_url}"'
        )
        content = content.replace(
            '"daisy-consulting-extrat-plast7-test-33133732"',
            f'"{odoo_db}"'
        )
        content = content.replace(
            '"im-it@daisyconsulting.ma"',
            f'"{odoo_user}"'
        )
        content = content.replace(
            '"odoo"',
            f'"{odoo_pass}"'
        )
        content = content.replace(
            "Odoo 19",
            f"Odoo {odoo_ver}"
        )

        with open(review_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✅ claude_review_v2.py configuré")

    # ── 5. Configuration e2e.py ───────────────────────────────────────────
    print("\n⚙️  Configuration e2e.py...")
    e2e_path = os.path.join(target, "e2e.py")
    if os.path.exists(e2e_path):
        with open(e2e_path, encoding="utf-8") as f:
            content = f.read()

        content = content.replace(
            "mohammedaminedahmani-tech/extraplast_modules",
            github_repo
        )
        content = content.replace(
            "https://daisy-consulting-extrat-plast7-test-33773518.dev.odoo.com",
            odoo_url
        )

        with open(e2e_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✅ e2e.py configuré")

    # ── 6. Résumé final ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅ Installation terminée !")
    print("=" * 60)
    print("\n📌 Étapes suivantes :")
    print("   1. Copie ta base ChromaDB dans le projet")
    print("   2. Ajoute les secrets GitHub (CLAUDE_CODE_OAUTH_TOKEN, PAT_TOKEN)")
    print("   3. Crée les issues GitHub #3, #4, #9")
    print("   4. Remplis projet.md avec ton cahier des charges")
    print("   5. Lance : pip install -r requirements.txt")
    print("   6. Lance : pre-commit install --config .pre-commit-config-v2.yaml")
    print("\n📖 Consulte SETUP.md pour plus de détails")
    print("=" * 60)

if __name__ == "__main__":
    main()