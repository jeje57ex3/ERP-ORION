"""Une erreur 500 au premier chargement, puis plus rien.

Symptôme constaté en production : après un redémarrage du serveur ou une
mise à jour, la première page affiche une erreur 500 ; un simple
rechargement suffit à la faire disparaître, et le journal ne dit rien de
compréhensible.

La cause est dans la source de Django, et elle se lit :

    def close_if_unusable_or_obsolete(self):
        if self.connection is not None:
            ...
            if self.errors_occurred:          # seulement APRÈS une erreur
                if self.is_usable(): ...
            if self.close_at is not None and time.monotonic() >= self.close_at:
                self.close()

Django ne teste la connexion que si une erreur s'est **déjà** produite, ou
si elle a dépassé `CONN_MAX_AGE`. Avec `CONN_MAX_AGE = 60`, chaque worker
gunicorn garde sa connexion MySQL ouverte ; quand MariaDB redémarre, le
worker conserve une socket morte qu'il croit saine, jeune et sans erreur.
La première requête échoue donc en 500 (« MySQL server has gone away »),
cette erreur marque la connexion, la requête suivante la ferme — et tout
revient à la normale.

Un 500 qui s'auto-répare est le signe de ce défaut, et pas d'un bug de
page : c'est pourquoi il ne se reproduisait dans aucun test.

`CONN_HEALTH_CHECKS = True` (Django 4.1+) fait vérifier la connexion une
fois par requête, avec reconnexion silencieuse. Django le laisse à `False`
par défaut — `conn.setdefault("CONN_HEALTH_CHECKS", False)` dans
`ConnectionHandler.configure_settings`.

**Pourquoi ces tests lisent la source et non `settings.DATABASES`.**
`settings/testing.py` remplace entièrement `DATABASES` par un SQLite en
mémoire ; la configuration de production n'est donc jamais chargée pendant
les tests. Vérifier l'objet `settings` ne prouverait rien sur ce qui tourne
sur la VM. On vérifie donc le fichier, et la règle qu'il doit respecter :
**tout `CONN_MAX_AGE` non nul s'accompagne d'un `CONN_HEALTH_CHECKS`.**
"""

import os
import re

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Les fichiers où une base de données est configurée. Les bases entreprises
# sont ajoutées dynamiquement à settings.DATABASES par
# company_database_service, et portaient exactement le même défaut : une
# par entreprise, donc un 500 par entreprise après chaque redémarrage.
FICHIERS_DE_CONFIGURATION = [
    os.path.join('erp_btp', 'settings', 'base.py'),
    os.path.join('erp_btp', 'settings', 'production.py'),
    os.path.join('apps', 'core', 'company_database_service.py'),
]

MOTIF_MAX_AGE = re.compile(r"""['"]CONN_MAX_AGE['"]\s*:\s*([^,\n}]+)""")
MOTIF_SANTE = re.compile(r"""['"]CONN_HEALTH_CHECKS['"]\s*:\s*True""")


def _lire(relatif):
    chemin = os.path.join(RACINE, relatif)
    if not os.path.isfile(chemin):
        return None
    with open(chemin, encoding='utf-8-sig', errors='replace') as flux:
        return flux.read()


def test_toute_connexion_persistante_a_son_controle_de_sante():
    """La règle qui empêche le défaut de revenir.

    Une connexion persistante sans contrôle de santé est une erreur 500
    garantie au prochain redémarrage de la base. Si un jour une nouvelle
    base est configurée avec CONN_MAX_AGE et sans ce réglage, ce test le
    dira avant la production.
    """
    fautifs = []
    for relatif in FICHIERS_DE_CONFIGURATION:
        source = _lire(relatif)
        if source is None:
            continue
        for trouve in MOTIF_MAX_AGE.finditer(source):
            valeur = trouve.group(1).strip()
            if valeur in ('0', 'None'):
                continue  # pas de connexion persistante : rien à vérifier
            # Le réglage doit figurer dans le même dictionnaire ; on se
            # contente du même fichier, ce qui suffit à attraper l'oubli.
            if not MOTIF_SANTE.search(source):
                ligne = source[:trouve.start()].count('\n') + 1
                fautifs.append(f'{relatif}:{ligne} — CONN_MAX_AGE={valeur}')

    assert not fautifs, (
        "CONN_MAX_AGE non nul sans CONN_HEALTH_CHECKS : la première requête "
        "suivant un redémarrage de la base répondra 500, puis se réparera "
        "d'elle-même au rechargement — un symptôme presque impossible à "
        "diagnostiquer depuis les journaux.\n  " + '\n  '.join(fautifs))


def test_la_base_par_defaut_a_le_controle_de_sante():
    source = _lire(os.path.join('erp_btp', 'settings', 'base.py'))
    assert source is not None
    assert MOTIF_SANTE.search(source), (
        "settings/base.py configure CONN_MAX_AGE sans CONN_HEALTH_CHECKS.")


def test_les_bases_entreprise_ont_le_controle_de_sante(db):
    """Test de comportement, lui : on lit le dictionnaire réellement produit.

    register_company_database construit la configuration à la main, champ
    par champ ; elle ne copie pas celle de « default » et peut donc
    divergier sans que rien ne le signale.
    """
    from django.conf import settings
    from django.db import connections

    from apps.core.company_database_service import (
        get_company_database_alias,
        register_company_database,
    )
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Dupont SA', slug='dupont-sa')
    alias = get_company_database_alias(entreprise)

    # NETTOYAGE OBLIGATOIRE, et la raison vaut d'être écrite :
    # register_company_database écrit directement dans settings.DATABASES un
    # dictionnaire qui ne porte PAS les clés que Django ajoute lui-même
    # (ATOMIC_REQUESTS, AUTOCOMMIT, TEST...). Laisser cet alias derrière soi
    # fait échouer en KeyError tout test ultérieur touchant au gestionnaire
    # de connexions — mesuré : 425 échecs en cascade.
    #
    # `connections.settings` est une cached_property : il faut aussi la
    # vider, sinon la configuration fautive survit à la suppression de
    # l'alias.
    presente_avant = alias in settings.DATABASES
    try:
        configuration = register_company_database(entreprise)

        assert configuration['CONN_MAX_AGE'] == 60
        assert configuration['CONN_HEALTH_CHECKS'] is True
        assert settings.DATABASES[alias]['CONN_HEALTH_CHECKS'] is True
    finally:
        if not presente_avant:
            settings.DATABASES.pop(alias, None)
        connections.__dict__.pop('settings', None)


def test_le_reglage_atteint_bien_la_connexion(tmp_path, db):
    """Preuve que la clé n'est pas seulement décorative.

    Django la lit dans `settings_dict` au moment de se connecter :
        self.health_check_enabled = self.settings_dict["CONN_HEALTH_CHECKS"]

    Sur une connexion JETABLE, et c'est voulu : la base de test est un
    SQLite « :memory: », et la fermer pour la rouvrir détruirait toutes ses
    tables au milieu de la suite. Un fichier temporaire à nous établit la
    même chaîne réglage → wrapper sans rien risquer.

    La fixture `db` est nécessaire bien qu'on n'écrive rien : pytest-django
    interdit TOUT accès base hors test marqué, en remplaçant
    `BaseDatabaseWrapper.ensure_connection` globalement — y compris pour
    une connexion qui n'est pas celle de Django.
    """
    from django.db.utils import ConnectionHandler

    for attendu in (True, False):
        handler = ConnectionHandler({'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': str(tmp_path / f'jetable-{attendu}.sqlite3'),
            'CONN_MAX_AGE': 60,
            'CONN_HEALTH_CHECKS': attendu,
        }})
        connexion = handler['default']
        try:
            connexion.connect()
            assert connexion.health_check_enabled is attendu
        finally:
            connexion.close()


def test_django_laisse_le_controle_desactive_par_defaut():
    """La raison pour laquelle l'oubli est facile.

    `conn.setdefault("CONN_HEALTH_CHECKS", False)` : ne rien écrire donne
    une connexion persistante jamais vérifiée. Si une version de Django
    changeait ce défaut, ce test le signalerait — et la règle ci-dessus
    deviendrait superflue.
    """
    from django.db.utils import ConnectionHandler

    handler = ConnectionHandler({'default': {
        'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}})
    assert handler.settings['default']['CONN_HEALTH_CHECKS'] is False
    assert handler.settings['default']['CONN_MAX_AGE'] == 0
