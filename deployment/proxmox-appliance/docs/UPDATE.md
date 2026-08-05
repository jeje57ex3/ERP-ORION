# Mises à jour

## Commande

```bash
sudo /opt/orion/scripts/update_orion.sh
```

Étapes effectuées :

1. `apt-get update && apt-get upgrade` — paquets système Ubuntu.
2. `docker compose pull` + redémarrage — images MySQL/Redis.
3. Mise à jour des paquets Node globaux et des dépendances Python du venv
   (`pip install -r requirements.txt`).
4. `manage.py run_system_update --no-confirm` — délègue à
   `apps.system_updates` (sauvegarde préventive automatique, `git pull`,
   migrations, vérifications post-update — logique déjà existante, non
   dupliquée ici).
5. Reconstruction des frontends SIÈCLE/LUNEA (`npm run build`, URLs d'API
   figées à la construction).
6. Redémarrage des 4 services applicatifs + rechargement Nginx.

## Rollback

En cas de problème après une mise à jour :

```bash
sudo -u orion /opt/orion/backend/.venv/bin/python \
  /opt/orion/backend/manage.py rollback_system_update
```

## Nettoyage

```bash
sudo /opt/orion/scripts/cleanup.sh
```

Purge : logs applicatifs > 30 jours, journaux systemd (> 2 semaines / 500 Mo),
caches npm/pip, ressources Docker inutilisées, sauvegardes expirées, paquets
APT orphelins.

## Fréquence recommandée

Pas de mise à jour automatique programmée par défaut (contrairement aux
sauvegardes) — `update_orion.sh` modifie des composants sensibles (DB, code
applicatif) et mérite une exécution supervisée. L'ajouter à un cron si un
fonctionnement pleinement automatisé est souhaité :

```
# /etc/cron.d/orion-update (à créer manuellement si désiré)
0 4 * * 0 root /opt/orion/scripts/update_orion.sh >> /opt/orion/logs/update.log 2>&1
```
