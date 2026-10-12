# Modules et pages

Inventaire **généré depuis le code** : la navigation telle qu'un utilisateur la
voit, puis la liste technique des modules montés. Les adresses sont résolues par
Django, elles ne peuvent donc pas être périmées.

## Navigation (27 modules, 110 pages)

Le menu latéral s'adapte à l'entreprise active : un module désactivé pour une
entreprise disparaît de son menu. Les modules marqués *Super Admin* ne sont
visibles que par un compte superutilisateur.

### Modules métier

#### Mon dashboard

Entrée : `/mon-dashboard/`

#### Vue générale

Entrée : `/dashboard/`

#### CRM

Entrée : `/crm/`

| Page | Adresse |
|---|---|
| Clients | `/crm/clients/` |
| Prospects | `/crm/prospects/` |
| Opportunités | `/crm/opportunites/` |
| Contacts | `/crm/contacts/` |

#### Ventes

Entrée : `/sales/`

| Page | Adresse |
|---|---|
| Devis | `/sales/devis/` |
| Commandes | `/sales/commandes/` |
| Factures | `/sales/factures/` |

#### Comptabilité

Entrée : `/accounting/`

#### Achats

Entrée : `/purchases/`

| Page | Adresse |
|---|---|
| Fournisseurs | `/purchases/fournisseurs/` |
| Commandes achat | `/purchases/commandes/` |
| Factures achat | `/purchases/factures/` |

#### Stocks

Entrée : `/inventory/`

| Page | Adresse |
|---|---|
| Produits | `/inventory/produits/` |
| Entrepôts | `/inventory/entrepots/` |
| Mouvements | `/inventory/mouvements/` |

#### BTP

Entrée : `/btp/`

| Page | Adresse |
|---|---|
| Tableau de bord | `/btp/responsable/` |
| Chantiers | `/btp/chantiers/` |
| Devis BTP | `/btp/devis/` |
| Demandes guidées | `/btp/demandes-guidees/` |
| Bibliothèque de prix | `/btp/tarifs-electricite/` |
| Frais de déplacement | `/btp/frais-deplacement/` |
| Pointages | `/btp/pointage/` |
| Situations | `/btp/situations/` |
| Réserves | `/btp/reserves/` |
| Messages clients | `/btp/messages-clients/` |
| Journal chantier | `/chantier/` |

#### E-commerce

Entrée : `/ecommerce/`

| Page | Adresse |
|---|---|
| Commandes web | `/ecommerce/commandes/` |
| Catalogue | `/ecommerce/catalogue/` |
| Expéditions | `/ecommerce/expeditions/` |
| Retours | `/ecommerce/retours/` |

#### Profils beauté

Entrée : `/beaute/`

| Page | Adresse |
|---|---|
| Dashboard | `/beaute/` |
| Profils | `/beaute/profils/` |
| Recommandations | `/beaute/recommandations/` |
| Diagnostics | `/beaute/diagnostics/` |
| Routines | `/beaute/routines/` |

#### SIÈCLE Créations

Entrée : `/creations/`

| Page | Adresse |
|---|---|
| Dashboard | `/creations/` |
| Catalogue | `/creations/catalogue/` |
| Collections | `/creations/collections/` |
| Commandes | `/creations/campagnes/` |

#### Commerce

Entrée : `/commerce/`

| Page | Adresse |
|---|---|
| Caisse | `/commerce/caisses/` |
| Magasins | `/commerce/magasins/` |
| Fidélité | `/commerce/fidelite/` |

#### Production

Entrée : `/production/`

| Page | Adresse |
|---|---|
| Ordres fabrication | `/production/ordres/` |
| Nomenclatures | `/production/nomenclatures/` |
| Planning | `/production/centres/` |

#### Audio / AV

Entrée : `/audio/`

| Page | Adresse |
|---|---|
| Matériel | `/audio/materiel/` |
| Réservations | `/audio/reservations/` |
| Événements | `/audio/evenements/` |

#### RH

Entrée : `/hr/`

| Page | Adresse |
|---|---|
| Salariés | `/hr/salaries/` |
| Congés | `/hr/conges/` |
| Notes de frais | `/hr/frais/` |
| Paie | `/paie/` |

#### Documents

Entrée : `/documents/`

#### Support

Entrée : `/support/`

| Page | Adresse |
|---|---|
| Tickets | `/support/tickets/` |
| Réclamations | `/support/reclamations/` |

#### Sites web

Entrée : `/websites/`

| Page | Adresse |
|---|---|
| Mes sites | `/websites/sites/` |
| Domaines | `/websites/domaines/` |
| Pages | `/websites/pages/` |
| Blog | `/websites/blog/` |
| Messages | `/websites/messages/` |
| Boutique | `/erp/websites/shop-settings/` |

#### Automatisations & IA

Entrée : `/alertes/`

| Page | Adresse |
|---|---|
| Alertes | `/alertes/` |
| Automatisations | `/automatisations/` |
| Workflows | `/workflows/` |
| Planification IA | `/planning/` |
| Analytique | `/analytique/` |
| Documents IA | `/docs/` |
| Assistant Orion | `/assistant/` |

#### Qualité & Conformité

Entrée : `/qualite/`

| Page | Adresse |
|---|---|
| Incidents | `/qualite/` |
| Audit | `/audit/` |
| Contrôle accès | `/acces/` |
| Intégrations | `/integrations/` |

#### Amélioration continue

Entrée : `/erp/pdca/`

| Page | Adresse |
|---|---|
| Tableau de bord | `/erp/pdca/` |
| Cycles PDCA | `/erp/pdca/cycles/` |
| Nouveau cycle | `/erp/pdca/cycles/nouveau/` |
| Standards | `/erp/pdca/standards/` |
| Modèles | `/erp/pdca/modeles/` |

#### Reporting

Entrée : `/bi/`

#### Analyse concurrence

Entrée : `/concurrents/`

| Page | Adresse |
|---|---|
| Dashboard | `/concurrents/` |
| Concurrents | `/concurrents/liste/` |
| Produits | `/concurrents/produits/` |
| Prix & historique | `/concurrents/prix/` |
| Trafic estimé | `/concurrents/trafic/` |
| Avantages | `/concurrents/avantages/` |
| Comparaison | `/concurrents/comparaison/` |
| Alertes | `/concurrents/alertes/` |
| Rapports | `/concurrents/rapports/` |

#### Sauvegardes

Entrée : `/sauvegardes/`

| Page | Adresse |
|---|---|
| Dashboard | `/sauvegardes/` |
| Sauvegardes | `/sauvegardes/liste/` |
| Planification | `/sauvegardes/planification/` |
| Créer | `/sauvegardes/creer/` |
| Paramètres | `/sauvegardes/parametres/` |

#### Assistant IA

Entrée : `/erp/assistant/`

| Page | Adresse |
|---|---|
| Chat IA | `/erp/assistant/` |
| Conversations | `/erp/assistant/conversations/` |
| Mémoire IA | `/erp/assistant/memoire/` |
| Paramètres IA | `/erp/assistant/parametres/` |

#### Paramètres

| Page | Adresse |
|---|---|
| Mon profil | `/accounts/profile/` |
| Utilisateurs | `/accounts/users/` |
| Entreprises | `/dashboard/companies/` |
| Administration | `/admin/` |

### Administration (Super Admin)

#### Super Admin

Entrée : `/orion-admin/`

| Page | Adresse |
|---|---|
| Dashboard | `/orion-admin/` |
| Entreprises | `/orion-admin/entreprises/` |
| Santé | `/orion-admin/sante/` |
| Santé du système | `/orion-admin/sante-systeme/` |
| Disques & stockage | `/orion-admin/sante-systeme/disques/` |
| Observabilité | `/systeme/` |
| Mises à jour | `/orion-admin/system-updates/` |
| Centre sauvegardes | `/backups/` |
| Haute dispo. | `/orion-admin/ha/settings/` |
| Nœuds HA | `/orion-admin/ha/nodes/` |
| Basculement HA | `/orion-admin/ha/failover/` |
| Paramètres | `/orion-admin/parametres/` |
| IA — Paramètres | `/orion-admin/ai/settings/` |
| IA — Audit | `/orion-admin/ai/audit/` |

## Inventaire technique

**62 modules** montés dans `erp_btp/urls.py`, pour **2044 routes**.
Tous ne sont pas exposés dans le menu : certains ne servent que des API, des
webhooks ou des pages publiques.

| Namespace | Préfixe d'URL | Routes |
|---|---|---|
| `access_control` | `/acces/` | 13 |
| `accounting` | `/accounting/` | 28 |
| `accounts` | `/accounts/` | 7 |
| `admin` | `/admin/` | 1169 |
| `api` | `/api/v1/` | 55 |
| `api_webhooks` | `/webhooks/` | 4 |
| `audio` | `/audio/` | 13 |
| `audit_compliance` | `/audit/` | 2 |
| `backup_center` | `/backups/` | 4 |
| `backups` | `/sauvegardes/` | 16 |
| `bi` | `/bi/` | 14 |
| `btp` | `/btp/` | 37 |
| `btp_smart_site_log` | `/chantier/` | 4 |
| `client_portal` | `/client/` | 18 |
| `commerce` | `/commerce/` | 12 |
| `competitor` | `/concurrents/` | 16 |
| `configurator` | `/configurateur/` | 5 |
| `continuous_improvement` | `/` | 29 |
| `core` | `/dashboard/` | 18 |
| `crm` | `/crm/` | 29 |
| `customer_360` | `/clients/360/` | 3 |
| `dashboard` | `/mon-dashboard/` | 12 |
| `dashboard_widgets` | `/` | 1 |
| `documents` | `/documents/` | 6 |
| `domain_diagnostics` | `/diagnostic-domaines/` | 8 |
| `ecommerce` | `/ecommerce/` | 67 |
| `ecommerce_auth` | `/api/v1/auth/customer/` | 5 |
| `ecommerce_lunea` | `/api/v1/lunea/store/` | 10 |
| `ecommerce_siecle` | `/api/v1/siecle/` | 10 |
| `guided_quote` | `/devis-guide/` | 6 |
| `high_availability` | `/` | 10 |
| `hr` | `/hr/` | 24 |
| `integration_center` | `/integrations/` | 3 |
| `inventory` | `/inventory/` | 13 |
| `launch` | `/` | 4 |
| `lunea` | `/api/v1/lunea/` | 30 |
| `lunea_beauty_profile` | `/beaute/` | 7 |
| `notifications` | `/notifications/` | 6 |
| `orion_ai` | `/` | 14 |
| `orion_assistant` | `/assistant/` | 5 |
| `payroll` | `/paie/` | 1 |
| `portals` | `/portails/` | 6 |
| `predictive_analytics` | `/analytique/` | 2 |
| `private_saas` | `/orion-admin/` | 9 |
| `production` | `/production/` | 11 |
| `public_websites` | `/sites/` | 39 |
| `purchases` | `/purchases/` | 19 |
| `quality_incidents` | `/qualite/` | 4 |
| `sales` | `/sales/` | 20 |
| `siecle_creations` | `/creations/` | 7 |
| `smart_alerts` | `/alertes/` | 6 |
| `smart_automations` | `/automatisations/` | 6 |
| `smart_documents` | `/docs/` | 2 |
| `smart_planning` | `/planning/` | 2 |
| `store` | `/boutique/` | 19 |
| `support` | `/support/` | 9 |
| `system_health` | `/` | 22 |
| `system_observability` | `/systeme/` | 5 |
| `system_updates` | `/` | 9 |
| `website_shop_settings` | `/` | 18 |
| `websites` | `/websites/` | 87 |
| `workflow_center` | `/workflows/` | 4 |

## Lire une adresse

Les noms de routes suivent la forme `namespace:nom`. Depuis un shell Django :

```python
from django.urls import reverse
reverse('system_health:disk_dashboard')   # -> /orion-admin/sante-systeme/disques/
```

C'est la façon fiable de retrouver une page : les préfixes changent, les noms de
routes beaucoup moins.

