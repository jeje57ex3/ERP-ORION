# Orion ERP Design System

Ce design system s'applique uniquement aux interfaces internes Orion ERP.

## Scope

Inclus :
- `/erp/`
- `/orion-admin/`
- dashboards
- modules internes
- Super Admin

Exclus :
- sites publics SIÈCLE
- sites publics LUNEA
- pages boutique publiques
- frontends publics

## Fichiers

| Fichier | Rôle |
|---|---|
| `orion-theme.css` | Variables CSS, palette, typographie |
| `orion-layout.css` | App shell, sidebar, page structure |
| `orion-components.css` | Cartes, boutons, alertes, métriques |
| `orion-forms.css` | Formulaires, inputs, selects |
| `orion-tables.css` | Tableaux de données |
| `orion-badges.css` | Badges et statuts |
| `orion-widgets.css` | Grille et cartes widgets dashboard |
| `orion-utilities.css` | Classes utilitaires |
| `orion-erp.css` | Import unique (point d'entrée) |

## Classes principales

- `.orion-page-header`, `.orion-page-title`, `.orion-page-subtitle`
- `.orion-page-eyebrow`
- `.orion-card`, `.orion-card-header`
- `.orion-btn`, `.orion-btn.primary`, `.orion-btn.danger`, `.orion-btn.sm`
- `.orion-table`
- `.orion-form`, `.orion-form-control`
- `.orion-badge`, `.orion-badge.success/warning/danger/info/gold`
- `.orion-dashboard-grid`, `.orion-metric-card`
- `.orion-widget-grid`, `.orion-widget-card`

## Palette

| Variable | Valeur | Usage |
|---|---|---|
| `--orion-bg` | `#0B0B0D` | Fond principal |
| `--orion-surface` | `#17171B` | Cartes |
| `--orion-gold` | `#D6B36A` | Accent principal |
| `--orion-text` | `#F7F2E7` | Texte principal |
| `--orion-success` | `#47C27A` | Succès |
| `--orion-warning` | `#E6A93E` | Avertissement |
| `--orion-danger` | `#E05252` | Erreur |

## Règles

- Aucun bouton bleu Bootstrap dans l'ERP
- Couleur principale ERP = or Orion (`#D6B36A`)
- Toute nouvelle page ERP étend `layouts/erp_shell.html`
- Toute nouvelle page utilise les classes `orion-*`

## Contrôle qualité

```bash
python scripts/check_erp_theme_consistency.py
```
