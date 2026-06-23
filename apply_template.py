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

    # ── 1b. .gitignore — AVANT tout git add ───────────────────────────────
    print("\n📝 Mise à jour .gitignore...")
    gitignore_path = os.path.join(project_dir, ".gitignore")
    entries_a_ajouter = ["odoo_global_db_*/", "chroma.sqlite3", "_template_tmp/"]
    lignes_existantes = set()
    if os.path.exists(gitignore_path):
        with open(gitignore_path, encoding="utf-8") as f:
            lignes_existantes = set(f.read().splitlines())
    with open(gitignore_path, "a", encoding="utf-8") as f:
        for entry in entries_a_ajouter:
            if entry not in lignes_existantes:
                f.write(f"\n{entry}")
    # Dé-stager si déjà tracké par erreur
    subprocess.run(f'git rm -r --cached odoo_global_db_*/ --ignore-unmatch',
                   shell=True, cwd=project_dir)
    subprocess.run(f'git rm --cached chroma.sqlite3 --ignore-unmatch',
                   shell=True, cwd=project_dir)
    print("   ✅ .gitignore configuré")

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

        # Remplacer repo et URL
        content = content.replace(
            "mohammedaminedahmani-tech/extraplast_modules",
            github_repo
        )
        content = content.replace(
            "https://daisy-consulting-extrat-plast7-test-33773518.dev.odoo.com/",
            odoo_url if odoo_url.endswith('/') else odoo_url + '/'
        )
        content = content.replace(
            '"im-it@daisyconsulting.ma"',
            f'"{odoo_user}"'
        )
        content = content.replace(
            'os.environ.get("ODOO_PASSWORD", "odoo")',
            f'os.environ.get("ODOO_PASSWORD", "{odoo_pass}")'
        )

        # Auto-générer MODULES depuis les dossiers du projet
        modules_dict = {}
        if os.path.exists(target):
            for dossier in sorted(os.listdir(target)):
                manifest = os.path.join(target, dossier, '__manifest__.py')
                if os.path.exists(manifest):
                    modules_dict[dossier] = {
                        'context': f'{sous_dossier}/{dossier}/CONTEXT.md',
                    }

        modules_str = "MODULES = {\n"
        for mod, cfg in modules_dict.items():
            modules_str += f"    '{mod}': {{\n"
            modules_str += f"        'context': '{cfg['context']}',\n"
            modules_str += f"    }},\n"
        modules_str += "}"

        content = content.replace("MODULES = {}", modules_str)

        with open(e2e_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"   ✅ e2e.py configuré ({len(modules_dict)} modules détectés)")

    # ── 7. Créer les CONTEXT.md vides pour chaque module ─────────────────
    print("\n📝 Création des CONTEXT.md...")
    context_template = """# CONTEXT.md — {module}

## Description
<!-- Décris brièvement ce que fait ce module -->

## Scénarios à tester
<!-- Liste les scénarios que Claude doit tester via Playwright -->

### Scénario 1 : ...
1. Aller sur ...
2. Cliquer sur ...
3. Vérifier que ...

### Scénario 2 : ...
1. ...
"""
    for dossier in sorted(os.listdir(target)):
        manifest = os.path.join(target, dossier, '__manifest__.py')
        if os.path.exists(manifest):
            context_path = os.path.join(target, dossier, 'CONTEXT.md')
            if not os.path.exists(context_path):
                with open(context_path, 'w', encoding='utf-8') as f:
                    f.write(context_template.format(module=dossier))
                print(f"   ✅ {dossier}/CONTEXT.md créé")
    print("   ✅ CONTEXT.md créés — remplis-les avant de lancer e2e.py")

    # ── 8. Suppression du template tmp ────────────────────────────────────
    print("\n🧹 Nettoyage...")
    rmtree_force(template_tmp)
    print("   ✅ Template temporaire supprimé")

    # ── 9. Installation des dépendances Python ────────────────────────────
    print("\n📦 Installation des dépendances Python...")
    req_path = os.path.join(project_dir, "requirements.txt")
    run(f'pip install -r "{req_path}"')
    print("   ✅ Dépendances Python installées")

    # ── 10. Installation Playwright ───────────────────────────────────────
    print("\n📦 Installation Playwright...")
    run("npm install playwright --legacy-peer-deps", cwd=project_dir, ignore_error=True)
    run("npx playwright install chromium", cwd=project_dir, ignore_error=True)
    print("   ✅ Playwright installé")

    # ── 11. Push ──────────────────────────────────────────────────────────
    print("\n🚀 Push vers GitHub...")
    # (le .gitignore a déjà été configuré à l'étape 1b — ne pas le refaire ici)

    run("git add .", cwd=target)
    run('git commit -m "chore: apply odoo-devops-template"', cwd=target, ignore_error=True)
    run("git push", cwd=target)
    run("git add .", cwd=project_dir, ignore_error=True)
    run('git commit -m "chore: add root devops files"', cwd=project_dir, ignore_error=True)
    run("git push", cwd=project_dir, ignore_error=True)
    print("   ✅ Push effectué")

    # ── 12. Auto-suppression du script ────────────────────────────────────
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
    print("   3. Crée les issues GitHub #1, #2, #3")
    print("   4. Crée le fichier .env avec tes credentials")
    print("   5. Remplis les CONTEXT.md de chaque module pour les tests E2E")
    print("   6. Remplis SETUP.md avec ton cahier des charges")
    print("=" * 60)


if __name__ == "__main__":
    main()
