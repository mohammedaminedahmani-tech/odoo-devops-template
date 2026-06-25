# Guide Final — Claude DevOps Odoo Template

Ce que fait ce système

•	Pre-commit v2 — Analyse automatique de ton code Odoo avant chaque commit

•	@claude — Assistant expert Odoo dans tes issues GitHub

•	E2E — Tests automatiques de bout en bout (configuration manuelle requise)

________________________________________

# Prérequis obligatoires

Installe ces outils avant de commencer :

Vérifie que tout est installé

git --version

python --version

claude --version

Si Claude Code CLI manque :

      npm install -g @anthropic-ai/claude-code

et pour la configuration du mcp playwright en local il faut lancer cette commande :

      claude mcp add playwright npx @playwright/mcp@latest -- --headless

docker --version

npm -- version  

node --version

si c pas installer on lance la commande ca intall npm et node :

      winget install OpenJS.NodeJS
________________________________________

# ÉTAPE 1 — Récupérer les tokens

Token Claude Code

Se connecter 
      
      claude auth login
      
Copier code 

      claude setup-token

Le token ressemble à : sk-ant-oat01-xxxxxxxxxxxxxxxx

Token GitHub (PAT)

1.	Va sur github.com → ton profil → Settings

2.	Developer settings → Personal access tokens → Tokens (classic)

3.	Generate new token → coche repo + workflow → Generate

4.	Copie le token affiché

Le token ressemble à : ghp_xxxxxxxxxxxxxxxxxxxx

________________________________________

# ÉTAPE 2 — Configurer les tokens (une seule fois par PC)

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

# ÉTAPE 3 — Créer les 3 issues GitHub

Dans ton repo → Issues → New issue :

Titre

#1	Claude Review — Rapports d'analyse

#2	Claude Chat Expert — Historique

#3	E2E Tests — Rapports

Les numéros doivent être exactement #1, #2, #3 dans cet ordre.

________________________________________

# ÉTAPE 5 — Configurer les secrets GitHub

Dans ton repo → Settings → Secrets and variables → Actions → New repository secret :

Nom	Valeur

CLAUDE_CODE_OAUTH_TOKEN	ton token Claude Code

PAT_TOKEN	ton Personal Access Token GitHub

GITHUB_TOKEN est automatique — ne pas l'ajouter.

________________________________________

# ÉTAPE 6 — Lancer le template

      cd "C:\Users\TON_NOM\Bureau"

      git clone https://github.com/Daisy-Consulting/CI-CD-Claude.git mon-projet-x

      cd mon-projet-x

      python apply_template.py

Répondre aux questions :

GitHub repo ? TON_ORG/mon-projet-odoo

Dossier parent ? C:\Users\TON_NOM\Bureau

Sous-dossier modules ? nom-du-dossier-modules s il n existe pas c lieu de le creer dans afin de ne rien modifier cote cote sinon il faut supprimer / danss tous les modules creer automatique de e2e.py

URL Odoo ? https://ton-instance.dev.odoo.com

DB Odoo ? nom-de-ta-base

Username Odoo ? ton@email.com

Password Odoo ? ton_mot_de_passe

Version Odoo ? 17 / 18 / 19 

pour la base s'il est 18 ou 19 il faut copier la base dans le dossier sinon pour la 17 elle n est pas dispo elle est bipasser

________________________________________

# ÉTAPE 7 — Créer le fichier .env

Dans la racine du projet (ex: Bureau/mon-projet-odoo/) crée .env :

copier le contenu de .env.exemple et remplire les donne 

ne jmais pusher ce fichier il est dans git ignore

________________________________________

# ÉTAPE 8 — Copier la base ChromaDB

on copie manuellement la base s il est dispo

La base doit être à la racine du projet au même niveau que claude_review_v2.py.

# Utilisation quotidienne

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

NB = au cas ou on veut tester plusieur module on peus il faut juste add tous les fichier souhaiter et add pre-commit_v2.py aussi

@claude — Poser une question dans GitHub

Dans l'issue  2 chat expert → nouveau commentaire :

@claude explique-moi ce module

@claude y a-t-il des bugs dans ce code ?

@claude comment améliorer cette fonction ?

________________________________________

# Ce qu'il faut éviter

•	❌ Ne jamais pusher le fichier .env

•	❌ Ne jamais mettre odoo_global_db_18.0/ dans le sous-dossier modules

•	❌ Ne pas lancer pre-commit depuis la racine — toujours depuis le sous-dossier modules

•	❌ Ne pas oublier de lancer Docker Desktop avant le pre-commit

________________________________________

# Que faire si le token expire ?

1. Se reconnecter

            claude auth login

            claude setup-token

2. Mettre à jour partout

            $path = "HKCU:\Environment"

            Set-ItemProperty -Path $path -Name "CLAUDE_CODE_OAUTH_TOKEN" -Value "nouveau_token"

            $env:CLAUDE_CODE_OAUTH_TOKEN = "nouveau_token"

3. Mettre à jour le .env

Modifie la ligne CLAUDE_CODE_OAUTH_TOKEN= dans .env

4. Mettre à jour les secrets GitHub

Settings → Secrets → CLAUDE_CODE_OAUTH_TOKEN → Update

________________________________________

# Checklist finale avant de commencer

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

# Erreurs fréquentes et solutions

Erreur	Cause	Solution

HTTP Error 401	Token GitHub expiré	Mettre à jour GITHUB_TOKEN

Invalid bearer token	Token Claude expiré	claude auth login + claude setup-token

MemoryExhaustion	Relancer une 2ème fois	pre-commit run --config ...

not a file	Mauvais dossier	cd sous-dossier-modules

Token vide dans VS Code	VS Code pas redémarré	Utiliser les 2 blocs permanent + immédiat

Collection does not exist	Mauvais chemin ChromaDB	Vérifier que odoo_global_db_18.0/ est à la racine

## Installation (une seule fois) au cas ca a pas telehcarger automatiquement depuis le script

Playwright + Chromium
      
      npm init -y
      npm install playwright
      npx playwright install chromium

Installer le hook pre-commit
      
      pre-commit install

## Pre-commit — Analyser du code

Depuis la racine du projet
      
      cd C:\Users\TON_NOM\Bureau\TON_REPO

Stager un fichier ou les fichier souhaiter tester 

      git add NOM_SOUS_DOSSIER\nom_module\models\fichier.py

Lancer l'analyse sur les fichiers stagés

      pre-commit run --config NOM_SOUS_DOSSIER\.pre-commit-config-v2.yaml

Lancer sur tous les fichiers juste pour voir s'il y a des conflit l analyse avec rapport et avec l autre commmande au cas ou on as bzn de lancer sur plusieur module on add plusieur module

      pre-commit run --config NOM_SOUS_DOSSIER\.pre-commit-config-v2.yaml --all-files

## E2E Tests — Tester les modules

Lister les modules disponibles
      
      python e2e.py --list

Tester un module
      
      python e2e.py --module=nom_module

Tester tous les modules
      
      python e2e.py --all

Reposter le dernier rapport sans relancer les tests
      
      python -c "from e2e import post_last_report; post_last_report()"


---

## Git — Commandes utiles

```bash
# Configurer un 2ème remote
git remote add daisy https://github.com/Daisy-Consulting/CI-CD-Claude.git
git push -u daisy main

# Push forcé après reset
git push --force-with-lease

# Retirer un fichier sensible du tracking
git rm --cached .env
git commit -m "fix: remove .env"
git push

# Annuler le dernier commit (fichiers conservés)
git reset HEAD~1

# Voir les remotes configurés
git remote -v
```
---

## Token Claude expiré

```bash
claude auth login
claude setup-token
```

---

## Libérer de l'espace disque

```powershell
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
npm cache clean --force
pip cache purge
```

## usuful prompmt to generete CONETEXT.md automatiquement juste en confirmant la PR mais a condition si t as les droits de creeation de branche
      
      @claude
      
      Lis TOUT le contenu du module `...........` :
      - __manifest__.py
      - Tous les fichiers Python dans models/
      - Tous les fichiers XML dans views/ et reports/
      - security/ir.model.access.csv
      - static/ si présent
      
      Lis également TOUTES ses dépendances déclarées dans __manifest__.py (depends) :
      - Pour chaque dépendance custom (pas base/stock/purchase/etc.), lis aussi tous ses fichiers
      
      Ensuite génère un fichier CONTEXT.md ultra-complet pour ce module contenant :
      1. Objectif et description du module
      2. Liste des dépendances avec leur rôle
      3. Tous les modèles étendus avec leurs champs ajoutés et méthodes
      4. Toutes les vues personnalisées avec leurs modifications
      5. Tous les rapports PDF avec leur contenu
      6. Les flux de processus complets (sous forme de schémas texte)
      7. Les points d'attention pour les agents AI
      8. Les scénarios à tester (max 2, simples et rapides)
      
      Le fichier doit être suffisamment détaillé pour qu'un agent AI puisse comprendre et tester ce module sans aucune information supplémentaire.
      
      Ensuite :
      1. Crée une branche
      2. Remplace le contenu de par le contenu généré
      3. Crée un Pull Request vers `test`



## usuful prompmt to generete CONETEXT.md version copier coller si t as pas les droits de creeation de branche
      
      @claude
      
      Lis TOUT le contenu du module .............; :
      
      manifest.py
      Tous les fichiers Python dans models/
      Tous les fichiers XML dans views/ et reports/
      security/ir.model.access.csv
      static/ si présent
      Lis également TOUTES ses dépendances déclarées dans manifest.py (depends) :
      
      Pour chaque dépendance custom (pas base/stock/purchase/etc.), lis aussi tous ses fichiers
      ensuite repond moi ici avec le contenue du fichier dont je peus copier coller sans aucun creation je veu que la reponse sois en message et je copis colle                   manuellement ce fichier contient :
      Objectif et description du module
      Liste des dépendances avec leur rôle
      Tous les modèles étendus avec leurs champs ajoutés et méthodes
      Toutes les vues personnalisées avec leurs modifications
      Tous les rapports PDF avec leur contenu
      Les flux de processus complets (sous forme de schémas texte)
      Les points d'attention pour les agents AI
      Les scénarios à tester (max 2, simples et rapides)
      Le fichier doit être suffisamment détaillé pour qu'un agent AI puisse comprendre et tester ce module sans aucune information supplémentaire.

## usuful prompmt to generete CONETEXT.md version interaction humain afin d avoir une bonne comprehension et il n invente pas des choses qui n existe pas vraiment ajuster pour les 2 mode avec droit de cration de branche ou sans 

      @claude
      Lis TOUT le contenu du module...
      (ta commande actuelle)
      
      Ensuite, AVANT de générer le CONTEXT.md :
      1. Liste les points que tu n'es pas sûr de comprendre
      2. Pose-moi maximum 5 questions sur les comportements métier
      3. Attends mes réponses
      4. Génère le CONTEXT.md final
      
            
