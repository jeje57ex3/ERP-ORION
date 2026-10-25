# Relevés de catalogues fabricants

Les CSV de ce dossier sont produits par `manage.py explorer_catalogue` à
partir des sites publics des fabricants, puis **versionnés** pour arriver
sur le serveur avec la mise à jour.

Pourquoi les versionner plutôt que les déposer à la main : explorer un
catalogue complet représente des milliers de requêtes — 1 704 fiches chez
Legrand, 6 706 chez Hager — soit plus d'une heure. Le faire une fois,
garder le résultat et le déployer comme du code évite de refaire ce travail
sur chaque machine, et laisse une trace de ce qui a été importé et quand.

## Les importer

```bash
# Une fois : cree les fournisseurs et les sources.
manage.py creer_sources_fabricants --entreprise <slug>

# Essai a blanc, puis ecriture reelle.
manage.py importer_releves_web --entreprise <slug>
manage.py importer_releves_web --entreprise <slug> --ecrire
```

Le nom du fichier détermine la source : `legrand.csv` part dans « Relevé
web Legrand ». Renommer un fichier sans le nom du fabricant le laisse de
côté, avec un avertissement.

## Ce que ces prix sont, et ne sont pas

Ce sont des **prix publics** — conseillé TTC chez Legrand, HT recommandé
chez Hager, aucun chez Soprema. Ce ne sont **pas** les prix auxquels
l'entreprise achète, remise professionnelle comprise.

Chaque article importé est donc marqué **« prix indicatif, à confirmer »**.
Décocher la case sur un article le protège définitivement : un import
ultérieur n'écrase jamais un prix confirmé.

Les prix TTC sont ramenés en HT à 20 %, le champ étant du HT.

## Ce que chaque fabricant donne

| Fabricant | Voie | Référence | Prix |
|---|---|---|---|
| Hager | sitemap du catalogue | oui, JSON-LD | HT recommandé, partiel |
| Legrand | sitemap du site | oui, `itemprop="sku"` | conseillé TTC, quasi complet |
| Soprema | liste d'adresses fournie | code à 8 chiffres | **aucun** |
| Schneider | — | — | — |

**Schneider n'est pas exploitable** : leur site ne sert aucune donnée
produit en HTML, l'adresse d'une référence renvoyant la page générique
« tous les produits ». Pour Schneider, passer par le tarif Excel du portail
distributeur et la source « Tarif Schneider Electric ».

**Soprema n'est pas énumérable** : leur `/sitemap.xml` renvoie une image
PNG et leur liste de produits est construite par le navigateur. Les fiches
se lisent une par une, depuis une liste d'adresses — voir
`explorer_catalogue --urls`.
