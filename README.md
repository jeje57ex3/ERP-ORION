# Orion ERP

ERP interne multi-modules pour la gestion de SIÈCLE Créations et LUNEA Beauty.
Développé en Django 5 + Python 3.12.

> **Dépôt privé.** Ne jamais partager les clés, tokens, fichiers `.env`, bases locales ou backups.

---

## Modules

| Module | Description |
|---|---|
| `orion_admin` | Interface d'administration interne Orion |
| `private_suite` | Espace privé — gestion avancée |
| `enterprise` | Fonctionnalités entreprise multi-sites |
| `system_updates` | Mises à jour système via git |
| `dashboard_widgets` | Widgets configurables du tableau de bord |
| `website_shop_settings` | Paramètres boutiques SIÈCLE / LUNEA |
| `continuous_improvement` | Suivi des améliorations et KPIs |
| `orion_ai` | Intégration IA (GPT-4o, analyse, génération) |
| `high_availability` | Réplication et haute disponibilité |
| `lunea_beauty_profile` | Profils beauté clients LUNEA |
| `siecle_creations` | Gestion créations SIÈCLE |
| `client_portal` | Portail client externe |
| `electricity` | Gestion facturation électricité |
| `core` | Noyau commun : menus, permissions, middlewares |

---

## Installation — Windows

```powershell
# 1. Cloner
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION

# 2. Environnement virtuel
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Dépendances
pip install -r requirements.txt

# 4. Variables d'environnement
Copy-Item .env.example .env
# Éditer .env avec les vraies valeurs

# 5. Base de données
python manage.py migrate

# 6. Lancer
python manage.py runserver
```

## Installation — Linux / macOS

```bash
# 1. Cloner
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION

# 2. Environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 3. Dépendances
pip install -r requirements.txt

# 4. Variables d'environnement
cp .env.example .env
# Éditer .env avec les vraies valeurs

# 5. Base de données
python manage.py migrate

# 6. Lancer
python manage.py runserver
```

---

## Architecture UI interne

L'interface interne Orion utilise un design system isolé (`orion-internal`) qui n'interfère
pas avec les boutiques publiques SIÈCLE et LUNEA.

```
static/orion/css/
├── orion-internal.css          # Point d'entrée (imports)
├── orion-core-theme.css        # Variables CSS, couleurs, typographie
├── orion-internal-layout.css   # App shell, sidebar, topbar
├── orion-internal-components.css
├── orion-internal-forms.css
├── orion-internal-tables.css
├── orion-internal-badges.css
├── orion-internal-widgets.css
├── orion-internal-utilities.css
└── orion-internal-overrides.css

templates/layouts/
├── orion_internal.html         # Layout standalone (Bootstrap 5.3.3 CDN)
├── orion_admin.html            # Extend orion_internal.html
├── private_suite.html
└── enterprise.html
```

**Règle absolue** : jamais de classes ou CSS `orion-internal` dans les templates publics
(`templates/store/`, `frontend/siecle-store/`, `frontend/lunea-store/`).

---

## Scripts de maintenance

```bash
# Vérifier les secrets avant commit
python scripts/check_secrets_before_commit.py

# Vérifier la cohérence du thème interne
python scripts/check_orion_internal_ui_consistency.py

# Vérifier qu'aucun CSS interne ne fuite vers les boutiques
python scripts/check_no_internal_theme_on_public_sites.py

# Détecter les doublons UI
python scripts/find_duplicate_internal_elements.py

# Commande management — audit UI
python manage.py orion_ui_cleanup
python manage.py orion_ui_cleanup --list-widgets
python manage.py orion_ui_cleanup --list-duplicates
```

---

## Sécurité — règles absolues

- **Ne jamais committer** : `.env`, bases SQLite locales, backups, `media/` clients,
  clés Stripe live (`sk_live_`), tokens API, fichiers `.pem` ou clés privées.
- Le hook `pre-commit` bloque automatiquement les commits contenant des secrets détectés.
- Toutes les variables sensibles doivent être dans `.env` (non commité).
- `.env.example` est le seul fichier d'environnement commité — avec des valeurs fictives.

---

## Branches

| Branche | Rôle |
|---|---|
| `main` | Production stable |
| `develop` | Intégration continue |
| `feature/*` | Nouvelles fonctionnalités |
| `hotfix/*` | Correctifs urgents production |

---

## Confidentialité

Ce dépôt est **privé**. Ne pas le rendre public. Ne pas partager l'URL avec des tiers
sans accord explicite. Les données clients, configurations de sites, et paramètres de
paiement ne doivent jamais apparaître dans ce dépôt.
