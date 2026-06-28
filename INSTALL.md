# ERP BTP Starter — Guide d'installation complet

## Prérequis

- Python 3.10+ (recommandé : 3.11 ou 3.12)
- XAMPP avec MySQL activé
- pip

---

## Étape 1 — Télécharger Python

Télécharger sur https://www.python.org/downloads/
Cocher "Add Python to PATH" lors de l'installation.

Vérifier :
```
python --version
pip --version
```

---

## Étape 2 — Démarrer XAMPP

1. Ouvrir XAMPP Control Panel
2. Démarrer **Apache** (optionnel, pour phpMyAdmin)
3. Démarrer **MySQL**
4. Ouvrir phpMyAdmin : http://localhost/phpmyadmin/

---

## Étape 3 — Créer la base de données MySQL

Dans phpMyAdmin ou en ligne de commande MySQL :

```sql
CREATE DATABASE erp_btp CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Si votre MySQL XAMPP a un mot de passe root, notez-le.

---

## Étape 4 — Créer l'environnement virtuel

```bash
# Dans le dossier erp-btp-starter
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / Mac
source venv/bin/activate
```

---

## Étape 5 — Installer les dépendances

```bash
pip install -r requirements.txt
```

En cas d'erreur avec `mysqlclient` sur Windows, installer d'abord :
```bash
pip install pipwin
pipwin install mysqlclient
```

Ou utiliser PyMySQL à la place :
```bash
pip install PyMySQL
```

Et ajouter dans `erp_btp/__init__.py` :
```python
import pymysql
pymysql.install_as_MySQLdb()
```

---

## Étape 6 — Configurer le .env

Copier `.env.example` en `.env` et adapter :

```env
SECRET_KEY=votre-cle-secrete-longue-et-aleatoire
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=erp_btp
DB_USER=root
DB_PASSWORD=           # Laisser vide si pas de mdp XAMPP
DB_HOST=127.0.0.1
DB_PORT=3306
```

---

## Étape 7 — Migrations Django

```bash
python manage.py makemigrations core
python manage.py makemigrations accounts
python manage.py makemigrations crm
python manage.py makemigrations sales
python manage.py makemigrations accounting
python manage.py makemigrations purchases
python manage.py makemigrations inventory
python manage.py makemigrations documents
python manage.py makemigrations hr
python manage.py makemigrations payroll
python manage.py makemigrations support
python manage.py makemigrations workflow
python manage.py makemigrations portals
python manage.py makemigrations btp
python manage.py makemigrations ecommerce
python manage.py makemigrations commerce
python manage.py makemigrations production
python manage.py makemigrations audio
python manage.py makemigrations bi
python manage.py makemigrations websites

# Appliquer toutes les migrations
python manage.py migrate
```

---

## Étape 8 — Créer le superadmin

```bash
python manage.py createsuperuser
```

Exemple :
- Username: admin
- Email: admin@erp.local
- Password: Admin@2024!

---

## Étape 9 — Fichiers statiques

```bash
python manage.py collectstatic --noinput
```

---

## Étape 10 — Données de démonstration

```bash
python manage.py create_demo_data
```

Cela crée :
- 5 entreprises (BTP, E-commerce, Commerce, Production, Audio)
- 7 utilisateurs (mdp : Demo@2024!)
- Clients, sites web, thèmes

---

## Étape 11 — Lancer le serveur

```bash
python manage.py runserver
```

Accéder à :
- **ERP** : http://localhost:8000/
- **Admin Django** : http://localhost:8000/admin/
- **Connexion** : http://localhost:8000/accounts/login/

---

## Comptes de démonstration

| Utilisateur   | Mot de passe | Rôle         | Entreprise         |
|---------------|--------------|--------------|---------------------|
| admin         | Admin@2024!  | Superadmin   | Toutes              |
| admin_btp     | Demo@2024!   | Admin        | BTP Lefèvre         |
| admin_ecom    | Demo@2024!   | Admin        | E-Shop Tendance     |
| admin_commerce| Demo@2024!   | Admin        | Martin Commerce     |
| admin_prod    | Demo@2024!   | Admin        | Industrie Rhône     |
| admin_audio   | Demo@2024!   | Admin        | SoundEvent          |
| commercial1   | Demo@2024!   | Commercial   | BTP Lefèvre         |

---

## Sites web publics de démonstration

Après création des données démo, accéder aux sites publics :

- BTP : http://localhost:8000/sites/btp-construction-lefevre/
- E-commerce : http://localhost:8000/sites/e-shop-tendance/
- Audio : http://localhost:8000/sites/soundevent-productions/

---

## Structure du projet

```
erp-btp-starter/
├── manage.py
├── requirements.txt
├── .env
├── .env.example
├── erp_btp/          # Configuration Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/             # Applications Django
│   ├── core/         # Entreprises, Audit, Connecteurs
│   ├── accounts/     # Utilisateurs, Rôles
│   ├── crm/          # Clients, Prospects, Opportunités
│   ├── sales/        # Devis, Commandes, Factures
│   ├── accounting/   # Comptabilité
│   ├── purchases/    # Achats, Fournisseurs
│   ├── inventory/    # Stocks, Produits
│   ├── documents/    # GED
│   ├── hr/           # RH, Congés, Frais
│   ├── payroll/      # Paie
│   ├── support/      # Tickets, SAV
│   ├── workflow/     # Validations
│   ├── btp/          # Chantiers BTP
│   ├── ecommerce/    # Commandes web
│   ├── commerce/     # Caisse, Magasins
│   ├── production/   # GPAO, OF
│   ├── audio/        # Matériel, Réservations
│   ├── bi/           # Reporting
│   ├── api/          # REST API
│   └── websites/     # Sites web publics
├── templates/        # Templates HTML
├── static/           # CSS, JS, Images
└── media/            # Fichiers uploadés
```

---

## Prochaines étapes — Phase 2 à 6

### Phase 2 — Enrichissement Sites web
- Éditeur de pages visuel
- Gestion des menus
- Upload d'images
- Blog complet
- Formulaires avancés

### Phase 3 — Modules ERP communs
- CRM avec pipeline Kanban
- Devis avec PDF
- Factures avec numérotation automatique
- Achats fournisseurs
- Gestion des stocks complète

### Phase 4 — Modules sectoriels
- BTP : Situations de travaux, pointage terrain
- E-commerce : Picking, packing, tracking
- Commerce : Caisse tactile, fidélité
- Production : MRP, GPAO complète
- Audio : Planning techniciens, contrats

### Phase 5 — Reporting & BI
- Dashboards graphiques (Chart.js)
- Export Excel/PDF
- Indicateurs temps réel

### Phase 6 — Sécurité & Production
- 2FA
- Permissions avancées
- API REST complète
- Connecteurs Shopify/Stripe
- Déploiement production

---

## Résolution de problèmes

### Erreur mysqlclient
```bash
# Option 1 : PyMySQL
pip install PyMySQL
# Ajouter dans erp_btp/__init__.py :
import pymysql
pymysql.install_as_MySQLdb()

# Option 2 : Windows binaires
pip install --only-binary=:all: mysqlclient
```

### Erreur de migration
```bash
python manage.py makemigrations --merge
python manage.py migrate --run-syncdb
```

### Réinitialiser les données démo
```bash
python manage.py create_demo_data --reset
```
