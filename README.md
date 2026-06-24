Guide Final — Claude DevOps Odoo Template

Ce que fait ce système

•	Pre-commit v2 — Analyse automatique de ton code Odoo avant chaque commit

•	@claude — Assistant expert Odoo dans tes issues GitHub

•	E2E — Tests automatiques de bout en bout (configuration manuelle requise)

________________________________________

Prérequis obligatoires

Installe ces outils avant de commencer :

# Vérifie que tout est installé

git --version

python --version        # 3.10+

node --version

claude --version        # Claude Code CLI

docker --version        # Docker Desktop doit être lancé

Si Claude Code CLI manque :

npm install -g @anthropic-ai/claude-code

________________________________________

ÉTAPE 1 — Récupérer les tokens

Token Claude Code

claude auth login       # Ouvre le navigateur — connecte-toi

claude setup-token      # Affiche ton token → copie-le

Le token ressemble à : sk-ant-oat01-xxxxxxxxxxxxxxxx

Token GitHub (PAT)

1.	Va sur github.com → ton profil → Settings

2.	Developer settings → Personal access tokens → Tokens (classic)

3.	Generate new token → coche repo + workflow → Generate

4.	Copie le token affiché

Le token ressemble à : ghp_xxxxxxxxxxxxxxxxxxxx

________________________________________

ÉTAPE 2 — Configurer les tokens (une seule fois par PC)

Lance ces commandes dans PowerShell — elles configurent les tokens de façon permanente ET immédiate :

# Permanent (toutes les futures sessions)

$path = "HKCU:\Environment"

Set-ItemProperty -Path $path -Name "GITHUB_TOKEN" -Value "ghp_xxxxxxxxxxxxxxxxxxxx"

Set-ItemProperty -Path $path -Name "PAT_TOKEN" -Value "ghp_xxxxxxxxxxxxxxxxxxxx"

Set-ItemProperty -Path $path -Name "CLAUDE_CODE_OAUTH_TOKEN" -Value "sk-ant-oat01-xxxxxxxx"



# Immédiat (session actuelle)

$env:GITHUB_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

$env:PAT_TOKEN = "ghp_xxxxxxxxxxxxxxxxxxxx"

$env:CLAUDE_CODE_OAUTH_TOKEN = "sk-ant-oat01-xxxxxxxx"

Vérifie :

echo $env:GITHUB_TOKEN

echo $env:PAT_TOKEN

echo $env:CLAUDE_CODE_OAUTH_TOKEN

Les 3 doivent afficher les tokens.

IMPORTANT : Utilise toujours les 2 blocs ensemble (permanent + immédiat). Le bloc permanent seul ne prend effet qu'au prochain démarrage de VS Code.

________________________________________

ÉTAPE 3 — Créer le repo GitHub

1.	Va sur github.com → New repository

2.	Nom : mon-projet-odoo → Private → Create

3.	Push ton code Odoo :

cd "ton-dossier-odoo"

git init

git add .

git commit -m "initial commit"

git branch -M main

git remote add origin https://github.com/TON_ORG/mon-projet-odoo.git

git push -u origin main

________________________________________

ÉTAPE 4 — Créer les 3 issues GitHub

Dans ton repo → Issues → New issue :

#	Titre

#1	Claude Review — Rapports d'analyse

#2	Claude Chat Expert — Historique

#3	E2E Tests — Rapports

Les numéros doivent être exactement #1, #2, #3 dans cet ordre.

________________________________________

ÉTAPE 5 — Configurer les secrets GitHub

Dans ton repo → Settings → Secrets and variables → Actions → New repository secret :

Nom	Valeur

CLAUDE_CODE_OAUTH_TOKEN	ton token Claude Code

PAT_TOKEN	ton Personal Access Token GitHub

GITHUB_TOKEN est automatique — ne pas l'ajouter.

________________________________________

ÉTAPE 6 — Lancer le template

cd "C:\Users\TON_NOM\Bureau"

git clone https://github.com/mohammedaminedahmani-tech/odoo-devops-template.git mon-projet-setup

cd mon-projet-setup

python apply_template.py

Répondre aux questions :

GitHub repo ? TON_ORG/mon-projet-odoo

Dossier parent ? C:\Users\TON_NOM\Bureau

Sous-dossier modules ? nom-du-dossier-modules

URL Odoo ? https://ton-instance.dev.odoo.com

DB Odoo ? nom-de-ta-base

Username Odoo ? ton@email.com

Password Odoo ? ton_mot_de_passe

Version Odoo ? 17 / 18 / 19

________________________________________

ÉTAPE 7 — Créer le fichier .env

Dans la racine du projet (ex: Bureau/mon-projet-odoo/) crée .env :

GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

ODOO_URL=https://ton-instance.dev.odoo.com

ODOO_DB=nom-de-ta-base

ODOO_USERNAME=ton@email.com

ODOO_PASSWORD=ton_mot_de_passe

CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-xxxxxxxx

PAT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

Ne jamais pusher ce fichier — il est déjà dans .gitignore.

________________________________________

ÉTAPE 8 — Copier la base ChromaDB

Copy-Item -Recurse "chemin\vers\odoo_global_db_18.0" "C:\Users\TON_NOM\Bureau\mon-projet-odoo\odoo_global_db_18.0"

La base doit être à la racine du projet au même niveau que claude_review_v2.py.

Final = claude mcp add playwright npx @playwright/mcp@latest -- --headless

Utilisation quotidienne

Pre-commit — Analyser du code

cd "mon-projet-odoo\nom-dossier-modules"

git add fichier_modifie.py

pre-commit run --config .pre-commit-config-v2.yaml

Claude va :

1.	Lire le cahier des charges (SETUP.md)

2.	Analyser le fichier avec RAG ChromaDB

3.	Interroger la base Odoo via MCP Docker

4.	Rendre un verdict COMMIT_OK ou COMMIT_ERREUR

5.	Poster le rapport dans l'issue #1

@claude — Poser une question dans GitHub

Dans n'importe quelle issue → nouveau commentaire :

@claude explique-moi ce module

@claude y a-t-il des bugs dans ce code ?

@claude comment améliorer cette fonction ?

________________________________________

Ce qu'il faut éviter

•	❌ Ne jamais stager claude_review_v2.py avec tes fichiers Odoo

•	❌ Ne jamais pusher le fichier .env

•	❌ Ne jamais mettre odoo_global_db_18.0/ dans le sous-dossier modules

•	❌ Ne pas lancer pre-commit depuis la racine — toujours depuis le sous-dossier modules

•	❌ Ne pas oublier de lancer Docker Desktop avant le pre-commit

________________________________________

Que faire si le token expire ?

# 1. Se reconnecter

claude auth login

claude setup-token      # Copie le nouveau token



# 2. Mettre à jour partout

$path = "HKCU:\Environment"

Set-ItemProperty -Path $path -Name "CLAUDE_CODE_OAUTH_TOKEN" -Value "nouveau_token"

$env:CLAUDE_CODE_OAUTH_TOKEN = "nouveau_token"



# 3. Mettre à jour le .env

# Modifie la ligne CLAUDE_CODE_OAUTH_TOKEN= dans .env



# 4. Mettre à jour les secrets GitHub

# Settings → Secrets → CLAUDE_CODE_OAUTH_TOKEN → Update

________________________________________

Checklist finale avant de commencer

•	[ ] Git, Python, Node.js, Claude Code CLI, Docker installés

•	[ ] Docker Desktop lancé

•	[ ] claude auth login + claude setup-token effectués

•	[ ] Tokens configurés (permanent + immédiat)

•	[ ] Repo GitHub créé avec le code Odoo

•	[ ] Issues #1, #2, #3 créées

•	[ ] Secrets GitHub configurés (CLAUDE_CODE_OAUTH_TOKEN + PAT_TOKEN)

•	[ ] Template lancé (python apply_template.py)

•	[ ] Fichier .env créé

•	[ ] Base ChromaDB copiée à la racine du projet

________________________________________

Erreurs fréquentes et solutions

Erreur	Cause	Solution

HTTP Error 401	Token GitHub expiré	Mettre à jour GITHUB_TOKEN

Invalid bearer token	Token Claude expiré	claude auth login + claude setup-token

MemoryExhaustion	Relancer une 2ème fois	pre-commit run --config ...

not a file	Mauvais dossier	cd sous-dossier-modules

Token vide dans VS Code	VS Code pas redémarré	Utiliser les 2 blocs permanent + immédiat

Collection does not exist	Mauvais chemin ChromaDB	Vérifier que odoo_global_db_18.0/ est à la racine
