# Orion UI — Unification du Design System Interne

## Vue d'ensemble

Le système Orion Internal unifie le design de toutes les interfaces internes de l'ERP :
ERP principal, Super Admin, Private Suite, Enterprise.

**Thème** : Fond sombre (`#0B0B0D`) + accents or (`#D6B36A`)  
**Font** : Inter (corps) + Poppins (titres)  
**Scope** : Toutes les pages ERP non-publiques

**À ne jamais toucher** : `templates/store/`, `templates/public/`, `templates/siecle/`, `templates/lunea/`, `frontend/siecle-store/`, `frontend/lunea-store/`

---

## Architecture CSS

```
static/orion/css/
├── orion-internal.css          ← Point d'entrée (@import tous les autres)
├── orion-core-theme.css        ← Variables CSS, typographie, couleurs
├── orion-internal-layout.css   ← App shell, page, topbar, footer, grilles
├── orion-internal-navigation.css ← Sidebar, nav items, breadcrumb
├── orion-internal-components.css ← Cards, boutons, alertes, metric cards
├── orion-internal-forms.css    ← Inputs, selects, checkboxes, toggles
├── orion-internal-tables.css   ← Tables, pagination, toolbar
├── orion-internal-badges.css   ← Badges, status dots, tags
├── orion-internal-widgets.css  ← Widget grid, stat cards, health grid
├── orion-internal-utilities.css ← Classes utilitaires
└── orion-internal-overrides.css ← Overrides Bootstrap 5 (scopés à .orion-internal)
```

### Variables clés

```css
--orion-bg:           #0B0B0D   /* Fond principal */
--orion-surface:      #17171B   /* Cards, panneaux */
--orion-gold:         #D6B36A   /* Couleur d'accentuation */
--orion-text:         #F7F2E7   /* Texte principal */
--orion-border:       rgba(214, 179, 106, 0.18)
```

---

## Layouts disponibles

| Fichier | Usage | Extend |
|---------|-------|--------|
| `layouts/orion_internal.html` | Layout de base — standalone (pas de extends) | — |
| `layouts/orion_admin.html` | Super Admin | orion_internal.html |
| `layouts/private_suite.html` | Private Suite | orion_internal.html |
| `layouts/enterprise.html` | Enterprise | orion_internal.html |
| `layouts/erp_shell.html` | ERP principal (legacy, conservé) | base.html |

### Blocs disponibles dans orion_internal.html

- `{% block title %}` — `<title>`
- `{% block body_class %}` — classes supplémentaires sur `<body>`
- `{% block shell_class %}` — classe du conteneur app shell
- `{% block sidebar %}` — sidebar complète (peut être remplacée)
- `{% block topbar %}` — barre du haut
- `{% block topbar_title %}` — titre dans la topbar
- `{% block topbar_actions %}` — boutons d'action topbar
- `{% block breadcrumb %}` — fil d'Ariane
- `{% block page_header %}` — en-tête de page (titre + actions)
- `{% block page_actions %}` — boutons d'action dans l'en-tête
- `{% block main_class %}` — classe du `<main>`
- `{% block content %}` — **contenu principal**
- `{% block footer %}` — pied de page
- `{% block extra_css %}` — CSS supplémentaire dans `<head>`
- `{% block extra_modals %}` — modals supplémentaires
- `{% block extra_js %}` — JS supplémentaire en bas de page

### Exemple d'utilisation

```html
{% extends "layouts/orion_internal.html" %}
{% load static %}

{% block title %}Ma Page{% endblock %}

{% block content %}
<div class="orion-widget-grid">
  <div class="orion-widget">
    <span class="orion-widget-icon bi bi-graph-up"></span>
    <div class="orion-widget-value">42</div>
    <div class="orion-widget-label">Projets actifs</div>
  </div>
</div>
{% endblock %}
```

---

## Classes CSS principales

### Boutons

```html
<button class="orion-btn primary">Valider</button>
<button class="orion-btn danger sm">Supprimer</button>
<button class="orion-btn outline">Annuler</button>
<button class="orion-btn ghost">Détails</button>
```

### Cards

```html
<div class="orion-card">
  <div class="orion-card-header">Titre</div>
  <div class="orion-card-body">Contenu</div>
  <div class="orion-card-footer">Pied</div>
</div>
```

### Badges / statuts

```html
<span class="orion-badge success">Actif</span>
<span class="orion-badge danger">Erreur</span>
<span class="orion-badge gold">Premium</span>
<span class="orion-status-dot success">En ligne</span>
```

### Tableaux

```html
<div class="orion-table-wrap">
  <div class="orion-table-toolbar">
    <span class="orion-table-toolbar-title">Liste</span>
    <div class="orion-table-toolbar-actions">...</div>
  </div>
  <div class="orion-table-scroll">
    <table class="orion-table">
      <thead><tr><th>Colonne</th></tr></thead>
      <tbody><tr><td>Valeur</td></tr></tbody>
    </table>
  </div>
  <div class="orion-pagination">...</div>
</div>
```

### Formulaires

```html
<div class="orion-form-group">
  <label class="orion-form-label">Champ <span class="orion-required">*</span></label>
  <input type="text" class="orion-form-control" placeholder="Valeur">
  <span class="orion-form-text">Texte d'aide</span>
</div>

<select class="orion-select">
  <option>Option 1</option>
</select>
```

### Widgets

```html
<div class="orion-widget-grid">
  <div class="orion-widget">
    <div class="orion-widget-value">1 234</div>
    <div class="orion-widget-label">Chiffre d'affaires</div>
    <div class="orion-widget-trend up"><i class="bi bi-arrow-up"></i> +8%</div>
  </div>
</div>
```

---

## Scripts de maintenance

```bash
# Vérifier la cohérence thème interne
python scripts/check_orion_internal_ui_consistency.py

# Vérifier qu'aucun thème interne ne fuite vers les sites publics
python scripts/check_no_internal_theme_on_public_sites.py

# Chercher les éléments dupliqués (widgets, blocs, nav modules)
python scripts/find_duplicate_internal_elements.py

# Migrer les extends vers orion_internal.html (preview d'abord)
python scripts/normalize_internal_template_extends.py --dry-run
python scripts/normalize_internal_template_extends.py

# Migrer les classes Bootstrap vers Orion classes (preview d'abord)
python scripts/normalize_internal_ui_classes.py --dry-run
python scripts/normalize_internal_ui_classes.py
```

---

## Commande de management

```bash
# Vérifier tout
python manage.py orion_ui_cleanup

# Lister les widgets enregistrés
python manage.py orion_ui_cleanup --list-widgets

# Chercher les doublons
python manage.py orion_ui_cleanup --list-duplicates
```

---

## Règles d'architecture

1. **orion_internal.html est autonome** — il inclut Bootstrap 5 CDN directement.
   Ne pas l'utiliser pour les pages publiques.

2. **Scope des overrides Bootstrap** — toutes les règles de `orion-internal-overrides.css`
   sont scopées à `html.orion-internal` ou `.orion-internal body` pour éviter
   de polluer les pages publiques.

3. **Ne jamais hardcoder #0d6efd** — utiliser `var(--orion-gold)`, `var(--orion-success)`, etc.

4. **Widget codes sont uniques** — le registre lève une `ValueError` si un code est enregistré
   deux fois. Utiliser `unregister_widget(code)` dans les tests pour nettoyer.

5. **Déduplication de menus** — utiliser `apps.core.menu_deduplication` si plusieurs apps
   contribuent au même menu sidebar.

---

## Tests

```bash
pytest tests/test_orion_ui_consistency.py -v
```

Couvre :
- Existence de tous les fichiers CSS
- Templates de layout et partials
- Pas de fuite thème interne vers sites publics
- Registre de widgets (détection de doublons)
- Déduplication de menus nav
- Pas de bleu Bootstrap dans les CSS Orion

---

## Compatibilité

L'ancien `erp_shell.html` (extends `base.html`) est conservé et continue de fonctionner
pour tous les modules ERP existants. La migration vers `orion_internal.html` se fait
progressivement, module par module, en utilisant `normalize_internal_template_extends.py`.
