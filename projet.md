# 🚀 Odoo DevOps Template — Guide de configuration

## Ce que fait ce template
- **Pre-commit v2** : Analyse du code avant chaque commit (RAG + MCP Odoo Live)
- **Claude Chat Expert** : Agent IA pour poser des questions sur le projet via GitHub Issues
- **E2E Tests** : Tests automatisés via Claude Code + MCP Playwright

---

## Prérequis à installer une seule fois

1. **Node.js** + Claude Code CLI :
```bash
   npm install -g @anthropic-ai/claude-code
   claude setup-token
```

2. **Python** + dépendances :
```bash
   pip install -r requirements.txt
```

3. **Docker Desktop** — pour MCP Odoo Live :
```bash
   cd mcp-odoo
   docker build -t mcp/odoo .
```

4. **Pre-commit** :
```bash
   pip install pre-commit
   pre-commit install --config .pre-commit-config-v2.yaml
```

---

## Configuration du projet (à faire pour chaque nouveau projet)

### 1. `claude_review_v2.py` — modifier ces lignes uniquement :

```python
GITHUB_REPO = "TON_ORG/TON_REPO"        # ex: mohammedaminedahmani-tech/Bonbino-confort-staging
GITHUB_ISSUE_NUM = 3                      # numéro de l'issue rapport pre-commit
FICHIER_PROJET = "projet.md"             # nom de ton fichier cahier des charges
ODOO_URL = "https://TON_INSTANCE.dev.odoo.com"
ODOO_DB = "TON_DATABASE"
ODOO_USERNAME = "ton@email.com"
ODOO_PASSWORD = "ton_mot_de_passe"
```

### 2. `e2e.py` — modifier ces lignes :

```python
ODOO_URL = "https://TON_INSTANCE.dev.odoo.com"
GITHUB_REPO = "TON_ORG/TON_REPO"
GITHUB_ISSUE_NUM = 9                      # numéro de l'issue rapport E2E
```

### 3. `.github/workflows/claude-expert.yml` — modifier :

```yaml
gh issue view 3 --comments   # numéro issue rapports pre-commit
gh issue view 4 --comments   # numéro issue chat expert
```

### 4. Secrets GitHub à configurer :
Dans `Settings > Secrets and variables > Actions` :

| Secret | Description |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Token Claude Code (`claude setup-token`) |
| `PAT_TOKEN` | GitHub Personal Access Token |

### 5. Base ChromaDB :
Copie ton dossier `odoo_global_db/` (base doc Odoo) à la racine du projet.

### 6. Issues GitHub à créer :

| Numéro | Titre |
|---|---|
| #3 | Claude Review — Rapports d'analyse |
| #4 | Claude Chat Expert — Historique |
| #9 | E2E Tests — Rapports |

### 7. `projet.md` :
Remplis ce fichier avec le cahier des charges du projet.

---

## Utilisation

### Pre-commit
```bash
# Automatique à chaque commit
git commit -m "feat: ..."

# Manuel sur un module
$env:ANALYSE_MODULE="nom_module"
pre-commit run --config .pre-commit-config-v2.yaml claude-review-v2-module

# Audit global
pre-commit run --config .pre-commit-config-v2.yaml claude-review-v2-audit
```

### Chat Expert
Aller dans