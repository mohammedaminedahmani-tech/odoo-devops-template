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

FICHIERS = [
    "claude_review_v2.py",
    ".pre-commit-config-v2.yaml",
    "e2e.py",
    "requirements.txt",
    "projet.md",
    ".env.example",
    "SETUP.md",
]

DOSSIERS = [
    ".github",
    "mcp-odoo",
]

# Fichiers/dossiers à supprimer du projet cible après installation
A_SUPPRIMER = [
    "apply_template.py",      # le script lui-même
    "_template_tmp",          # dossier template temporaire
    "odoo-devops-template",   # si cloné par erreur dans le projet
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

    # ── 2. Clone le repo cible ────────────────────────────────────────────
    print(f"\n📥 Clonage de {github_repo}...")
    if os.path.exists(project_dir):
        print(f"   ⚠️  Dossier {repo_name} existe déjà — on l'utilise tel quel")
    else:
        run(f'git clone https://github.com/{github_repo}.git "{project_dir}"')
        print(f"   ✅ Repo cloné")

    # ── 3. Dossier cible (sous-dossier des modules) ───────────────────────
    target = os.path.join(project_dir, sous_dossier)
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

    # ── 5. Copie des fichiers dans le sous-dossier ────────────────────────
    print("\n📦 Copie des fichiers DevOps...")
    for fichier in FICHIERS:
        src = os.path.join(template_tmp, fichier)
        dst = os.path.join(target, fichier)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"   ✅ {fichier} → {sous_dossier}/")
        else:
            print(f"   ⚠️  {fichier} introuvable")

    # .github et mcp-odoo à la RACINE du repo
    for dossier in DOSSIERS:
        src = os.path.join(template_tmp, dossier)
        dst = os.path.join(project_dir, dossier)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"   ✅ {dossier}/ → racine repo")
        else:
            print(f"   ⚠️  {dossier}/ introuvable")

    # ── 6. Configuration claude_review_v2.py ─────────────────────────────
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
        content = content.replace("Odoo 19", f"Odoo {odoo_ver}")
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✅ claude_review_v2.py configuré")

    # ── 7. Configuration e2e.py ───────────────────────────────────────────
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

    # ── 8. Nettoyage — suppression de ce qui ne doit pas rester ──────────
    print("\n🧹 Nettoyage du projet...")
    for item in A_SUPPRIMER:
        path = os.path.join(project_dir, item)
        if os.path.isdir(path):
            rmtree_force(path)
            print(f"   🗑️  {item}/ supprimé")
        elif os.path.isfile(path):
            os.remove(path)
            print(f"   🗑️  {item} supprimé")

    # Supprimer apply_template.py du sous-dossier aussi si copié
    apply_in_target = os.path.join(target, "apply_template.py")
    if os.path.exists(apply_in_target):
        os.remove(apply_in_target)
        print(f"   🗑️  apply_template.py supprimé du sous-dossier")

    # ── 9. Installation des dépendances ───────────────────────────────────
    print("\n📦 Installation des dépendances Python...")
    req_path = os.path.join(target, "requirements.txt")
    run(f'pip install -r "{req_path}"', cwd=project_dir)
    print("   ✅ Dépendances installées")

    print("\n🔧 Installation pre-commit...")
    run(
        f'pre-commit install --config .pre-commit-config-v2.yaml',
        cwd=target
    )
    print("   ✅ Pre-commit installé")

    # ── 10. Push vers GitHub ──────────────────────────────────────────────
    print("\n🚀 Push vers GitHub...")
    run("git add .", cwd=project_dir)
    run("git rm --cached odoo-devops-template 2>nul", cwd=project_dir, ignore_error=True)
    run('git commit -m "chore: apply odoo-devops-template"', cwd=project_dir)
    run("git pull --rebase", cwd=project_dir, ignore_error=True)
    run("git push", cwd=project_dir)
    print("   ✅ Push effectué")

    # ── 11. Résumé ────────────────────────────────────────────────────────
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