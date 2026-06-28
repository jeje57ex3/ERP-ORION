# Checklist thème unifié Orion ERP

## Pages à vérifier

- [ ] `/erp/`
- [ ] `/orion-admin/`
- [ ] `/orion-admin/system-health/`
- [ ] `/orion-admin/system-updates/`
- [ ] `/orion-admin/ha/settings/`
- [ ] `/erp/assistant/`
- [ ] `/erp/continuous-improvement/`
- [ ] `/erp/ideas/`
- [ ] `/erp/websites/shop-settings/`
- [ ] `/erp/siecle/creation/`
- [ ] `/erp/lunea/beauty-profiles/`

## À contrôler

- [ ] aucun bouton bleu Bootstrap
- [ ] tous les boutons principaux sont or (`#D6B36A`)
- [ ] cartes avec fond sombre (`#17171B`)
- [ ] textes lisibles (`#F7F2E7`)
- [ ] tableaux cohérents (headers en uppercase, hover doré)
- [ ] badges cohérents (success/warning/danger/info/gold)
- [ ] formulaires cohérents (fond dark, focus doré)
- [ ] widgets cohérents (grille auto-fit)
- [ ] mobile correct (sidebar responsive)
- [ ] sites publics SIÈCLE non modifiés
- [ ] sites publics LUNEA non modifiés

## Commandes de contrôle

```bash
python scripts/check_erp_theme_consistency.py
python scripts/replace_erp_ui_classes.py
python manage.py collectstatic --noinput
```
