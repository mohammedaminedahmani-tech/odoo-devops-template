# -*- coding: utf-8 -*-
"""
apply_template.py
=================
Clone le template odoo-devops et l'applique dans un projet cible.

Usage :
  git clone https://github.com/mohammedaminedahmani-tech/odoo-devops-template.git
  cd odoo-devops-template
  python apply_template.py
"""

import os
import sys
import shutil
import subprocess
import stat

TEMPLATE_REPO = "https://github.com/mohammedaminedahmani-tech/odoo-devops-template.git"

# Fichiers copiés à la RACINE du repo
FICHIERS_RACINE = [
    "claude_review_v2.py",
    "e2e.py",
    "requirements.txt",
    "projet.md",
    ".env.example",
    "SETUP.md",
]

# Fichiers copiés dans le SOUS-DOSSIER (là où est le .git)
FICHIERS_SOUS_DOSSIER = [
    ".pre-commit-config-v2.yaml",
]

# Dossiers copiés à la RACINE du repo
DOSSIERS_RACINE = [
    ".github",
    "mcp-odoo",
]

# Fichiers/dossiers à supprimer après installation
A_SUPPRIMER = [
    "_template_tmp",
    "odoo-devops-template",
]


def remove_readonly(func, path, excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def rmtree_force(path):
    shutil.rmtree(path, onerror=remove_readonly)


def run(cmd, cwd=None, ignore_error=False):
    r = subprocess.run(cmd, shell=True, cwd=cwd)
    if r.returncode != 0 and not ignore_error:
        print(f"❌ Erreur : {cmd}")
        sys.exit(1)


def main():
    print("=" * 60)
    print("   Odoo DevOps Template — Installation automatique")
    print("=" * 60)

    # ── 1. Infos ──────────────────────────────────────────────────────────
    print("\n📋 Configuration :")
    github_repo  = input("   GitHub repo cible (ex: org/Bonbino-confort-staging) ? ").strip()
    clone_parent = input("   Dossier parent du projet (ex: C:\\Users\\DAHMANI\\OneDrive\\Bureau) ? ").strip().strip('"')
    sous_dossier = input("   Nom du sous-dossier des modules ? ").strip()
    odoo_url     = input("   URL Odoo ? ").strip()
    odoo_db      = input("   DB Odoo ? ").strip()
    odoo_user    = input("   Username Odoo ? ").strip()
    odoo_pass    = input("   Password Odoo ? ").strip()
    odoo_ver     = input("   Version Odoo (17/18/19) ? ").strip()

    repo_name   = github_repo.split("/")[-1]
    project_dir = os.path.join(clone_parent, repo_name)
    target      = os.path.join(project_dir, sous_dossier)

    # ── 2. Clone le repo cible ────────────────────────────────────────────
    print(f"\n📥 Clonage de {github_repo}...")
    if os.path.exists(project_dir):
        print(f"   ⚠️  Dossier {repo_name} existe déjà — on l'utilise tel quel")
    else:
        run(f'git clone https://github.com/{github_repo}.git "{project_dir}"')
        print(f"   ✅ Repo cloné")

    # ── 3. Dossier cible (sous-dossier des modules) ───────────────────────
    if not os.path.exists(target):
        os.makedirs(target)
        print(f"   ✅ Sous-dossier créé : {sous_dossier}/")

    # ── 4. Clone le template dans un dossier tmp ──────────────────────────
    print(f"\n📥 Téléchargement du template DevOps...")
    template_tmp = os.path.join(project_dir, "_template_tmp")
    if os.path.exists(template_tmp):
        rmtree_force(template_tmp)
    run(f'git clone {TEMPLATE_REPO} "{template_tmp}"')
    print(f"   ✅ Template téléchargé")

    # ── 5. Copie des fichiers à la RACINE ────────────────────────────────
    print("\n📦 Copie des fichiers DevOps à la racine...")
    for fichier in FICHIERS_RACINE:
        src = os.path.join(template_tmp, fichier)
        dst = os.path.join(project_dir, fichier)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"   ✅ {fichier} → racine/")
        else:
            print(f"   ⚠️  {fichier} introuvable")

    for dossier in DOSSIERS_RACINE:
        src = os.path.join(template_tmp, dossier)
        dst = os.path.join(project_dir, dossier)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"   ✅ {dossier}/ → racine/")
        else:
            print(f"   ⚠️  {dossier}/ introuvable")

    # ── 6. Copie des fichiers dans le SOUS-DOSSIER ───────────────────────
    print(f"\n📦 Copie des fichiers dans {sous_dossier}/...")
    for fichier in FICHIERS_SOUS_DOSSIER:
        src = os.path.join(template_tmp, fichier)
        dst = os.path.join(target, fichier)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"   ✅ {fichier} → {sous_dossier}/")
        else:
            print(f"   ⚠️  {fichier} introuvable")

    # ── 7. Configuration claude_review_v2.py ─────────────────────────────
    print("\n⚙️  Configuration claude_review_v2.py...")
    review_path = os.path.join(project_dir, "claude_review_v2.py")
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
        content = content.replace("Odoo 19", f"Odoo {odoo_ver}")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✅ claude_review_v2.py configuré")

    # ── 8. Configuration e2e.py ───────────────────────────────────────────
    print("\n⚙️  Configuration e2e.py...")
    e2e_path = os.path.join(project_dir, "e2e.py")
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

    # ── 9. Nettoyage ──────────────────────────────────────────────────────
    print("\n🧹 Nettoyage...")
    for item in A_SUPPRIMER:
        path = os.path.join(project_dir, item)
        if os.path.isdir(path):
            rmtree_force(path)
            print(f"   🗑️  {item}/ supprimé")
        elif os.path.isfile(path):
            os.remove(path)
            print(f"   🗑️  {item} supprimé")

    # ── 10. Installation des dépendances ──────────────────────────────────
    print("\n📦 Installation des dépendances Python...")
    req_path = os.path.join(project_dir, "requirements.txt")
    run(f'pip install -r "{req_path}"', cwd=project_dir)
    print("   ✅ Dépendances installées")



    # ── 12. Push vers GitHub ──────────────────────────────────────────────
    print("\n🚀 Push vers GitHub...")
    run("git add .", cwd=target)
    run('git commit --no-verify -m "chore: apply odoo-devops-template"', cwd=target, ignore_error=True)
    run("git add .", cwd=target)
    run('git commit --no-verify -m "chore: fix pre-commit auto-fixes"', cwd=target, ignore_error=True)
    
    run("git pull --rebase", cwd=target, ignore_error=True)
    run("git push", cwd=target)
    # Push aussi les fichiers racine
    run("git add .", cwd=project_dir, ignore_error=True)
    run('git commit -m "chore: add root devops files"', cwd=project_dir, ignore_error=True)
    run("git pull --rebase", cwd=project_dir, ignore_error=True)
    run("git push", cwd=project_dir, ignore_error=True)
    print("   ✅ Push effectué")

    # ── 13. Résumé ────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("✅ Installation terminée !")
    print("=" * 60)
    print("\n📌 Dernières étapes manuelles :")
    print("   1. Copie ta base ChromaDB odoo_global_db/ dans le projet")
    print("   2. Ajoute les secrets GitHub (CLAUDE_CODE_OAUTH_TOKEN, PAT_TOKEN)")
    print("   3. Crée les issues GitHub #3, #4, #9")
    print("   4. Remplis projet.md avec ton cahier des charges")
    print("\n📖 Consulte SETUP.md pour plus de détails")
    print("=" * 60)


if __name__ == "__main__":
    main()