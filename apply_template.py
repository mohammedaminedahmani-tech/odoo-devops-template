# -*- coding: utf-8 -*-
import os
import sys
import shutil
import subprocess
import stat

TEMPLATE_REPO = "https://github.com/mohammedaminedahmani-tech/odoo-devops-template.git"

FICHIERS_RACINE = [
    "claude_review_v2.py",
    "e2e.py",
    "requirements.txt",
    "projet.md",
    ".env.example",
    "SETUP.md",
]

FICHIERS_SOUS_DOSSIER = [
    ".pre-commit-config-v2.yaml",
]

DOSSIERS_RACINE = [
    ".github",
    "mcp-odoo",
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

    print("\n📋 Configuration :")
    github_repo  = input("   GitHub repo (ex: org/mon-projet) ? ").strip()
    clone_parent = input("   Dossier parent du projet ? ").strip().strip('"')
    sous_dossier = input("   Nom du sous-dossier des modules ? ").strip()
    odoo_url     = input("   URL Odoo ? ").strip()
    odoo_db      = input("   DB Odoo ? ").strip()
    odoo_user    = input("   Username Odoo ? ").strip()
    odoo_pass    = input("   Password Odoo ? ").strip()
    odoo_ver     = input("   Version Odoo (17/18/19) ? ").strip()

    repo_name   = github_repo.split("/")[-1]
    project_dir = os.path.join(clone_parent, repo_name)
    target      = os.path.join(project_dir, sous_dossier)

    # ── 1. Clone le repo cible ────────────────────────────────────────────
    print(f"\n📥 Clonage de {github_repo}...")
    if os.path.exists(project_dir):
        print(f"   ⚠️  Dossier {repo_name} existe déjà")
    else:
        run(f'git clone https://github.com/{github_repo}.git "{project_dir}"')
        print(f"   ✅ Repo cloné")

    if not os.path.exists(target):
        os.makedirs(target)

    # ── 2. Clone le template ──────────────────────────────────────────────
    print(f"\n📥 Téléchargement du template...")
    template_tmp = os.path.join(project_dir, "_template_tmp")
    if os.path.exists(template_tmp):
        rmtree_force(template_tmp)
    run(f'git clone {TEMPLATE_REPO} "{template_tmp}"')
    print(f"   ✅ Template téléchargé")

    # ── 3. Copie des fichiers à la RACINE ─────────────────────────────────
    print("\n📦 Copie des fichiers à la racine...")
    for fichier in FICHIERS_RACINE:
        src = os.path.join(template_tmp, fichier)
        dst = os.path.join(project_dir, fichier)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"   ✅ {fichier}")
        else:
            print(f"   ⚠️  {fichier} introuvable")

    for dossier in DOSSIERS_RACINE:
        src = os.path.join(template_tmp, dossier)
        dst = os.path.join(project_dir, dossier)
        if os.path.exists(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"   ✅ {dossier}/")
        else:
            print(f"   ⚠️  {dossier}/ introuvable")

    # ── 4. Copie des fichiers dans le SOUS-DOSSIER ────────────────────────
    print(f"\n📦 Copie dans {sous_dossier}/...")
    for fichier in FICHIERS_SOUS_DOSSIER:
        src = os.path.join(template_tmp, fichier)
        dst = os.path.join(target, fichier)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"   ✅ {fichier}")
        else:
            print(f"   ⚠️  {fichier} introuvable")

    # ── 5. Configuration claude_review_v2.py ──────────────────────────────
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
            'ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "odoo")',
            f'ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD", "{odoo_pass}")'
        )
        content = content.replace("Odoo 19", f"Odoo {odoo_ver}")
        content = content.replace(
            '"odoo_global_db"',
            f'"odoo_global_db_{odoo_ver}.0"'
        )
        with open(review_path, "w", encoding="utf-8") as f:
            f.write(content)
        print("   ✅ claude_review_v2.py configuré")

    # ── 6. Configuration e2e.py ───────────────────────────────────────────
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

    # ── 7. Suppression du template tmp ────────────────────────────────────
    print("\n🧹 Nettoyage...")
    rmtree_force(template_tmp)
    print("   ✅ Template temporaire supprimé")

    # ── 8. Installation des dépendances ───────────────────────────────────
    print("\n📦 Installation des dépendances Python...")
    req_path = os.path.join(project_dir, "requirements.txt")
    run(f'pip install -r "{req_path}"')
    print("   ✅ Dépendances installées")

    # ── 9. Push ───────────────────────────────────────────────────────────
    print("\n🚀 Push vers GitHub...")
    run("git add .", cwd=target)
    run('git commit -m "chore: apply odoo-devops-template"', cwd=target, ignore_error=True)
    run("git push", cwd=target)
    # Push les fichiers racine aussi
    run("git add .", cwd=project_dir, ignore_error=True)
    run('git commit -m "chore: add root devops files"', cwd=project_dir, ignore_error=True)
    run("git push", cwd=project_dir, ignore_error=True)
    print("   ✅ Push effectué")

    # ── 10. Auto-suppression du script ────────────────────────────────────
    print("\n🗑️  Suppression du script apply_template.py...")
    script_path = os.path.abspath(__file__)
    os.remove(script_path)
    print("   ✅ Script supprimé")

    print("\n" + "=" * 60)
    print("✅ Installation terminée !")
    print("=" * 60)
    print("\n📌 Étapes manuelles restantes :")
    print("   1. Copie ta base ChromaDB odoo_global_db/ dans le projet")
    print("   2. Ajoute les secrets GitHub (CLAUDE_CODE_OAUTH_TOKEN, PAT_TOKEN)")
    print("   3. Crée les issues GitHub #3, #4, #9")
    print("   4. Remplis projet.md avec ton cahier des charges")
    print("=" * 60)


if __name__ == "__main__":
    main()