"""La migration ecommerce.0004 doit pouvoir être rejouée sans échouer.

CE QUI EST ARRIVÉ EN PRODUCTION, le 07/11/2026. MySQL n'a pas de DDL
transactionnel : une migration interrompue laisse derrière elle les tables
qu'elle avait déjà créées, et n'écrit rien dans `django_migrations`. Django
la croit encore à faire, rejoue sa première opération, et MySQL répond
« (1050) Table ... already exists ».

L'état est ABSORBANT, et c'est ce qui le rend grave : chaque tentative
échoue à l'identique, donc `migrate` échoue, donc la mise à jour de l'ERP
échoue — donc plus aucun correctif ne peut être déployé, y compris le
correctif de ce défaut. Trois correctifs sont restés bloqués derrière
celui-là.

LE TEST QUI COMPTE VRAIMENT N'EST PAS DANS CE FICHIER : c'est la suite
entière, qui applique les VRAIES migrations sur une base neuve. Si cette
migration est cassée, tous les tests échouent à la création de la base —
c'est d'ailleurs ainsi qu'une première version de ce correctif a été
prise en défaut.

Les tests ci-dessous pincent ce que la suite ne voit pas : le comportement
quand la table existe DÉJÀ, qui est précisément le cas de production et
qu'une base neuve ne reproduit jamais.
"""

import importlib
import types

import pytest
from django.db import migrations as m

MODULE = ('apps.ecommerce.migrations.'
          '0004_savedwatchconfiguration_watchpreset_and_more')

MODELES = ('SavedWatchConfiguration', 'WatchPreset',
           'WatchCustomizationOption')

TABLES = ('ecommerce_savedwatchconfiguration',
          'ecommerce_watchpreset',
          'ecommerce_watchcustomizationoption')


@pytest.fixture
def migration():
    # import_module et non `import` : un nom de module qui commence par un
    # chiffre n'est pas un identifiant Python valide.
    return importlib.import_module(MODULE)


class _FauxEditeur:
    """Un schema_editor réduit à ce que l'opération lui demande."""

    def __init__(self, tables_existantes):
        self.connection = types.SimpleNamespace(
            alias='default',
            introspection=types.SimpleNamespace(
                table_names=lambda: list(tables_existantes)))


class _FauxEtat:
    """Le registre réel suffit : les trois modèles y sont déclarés."""

    def __init__(self):
        from django.apps import apps
        self.apps = apps


@pytest.fixture
def appels(monkeypatch):
    """Intercepte l'appel au CreateModel parent.

    On n'exécute pas le vrai `create_model` : il passerait par les routeurs
    de base de données de ce projet, qui en comptent plusieurs, et le test
    mesurerait alors leur avis plutôt que la décision testée ici.
    """
    faits = {'avant': [], 'arriere': []}
    monkeypatch.setattr(
        m.CreateModel, 'database_forwards',
        lambda self, *a, **k: faits['avant'].append(self.name))
    monkeypatch.setattr(
        m.CreateModel, 'database_backwards',
        lambda self, *a, **k: faits['arriere'].append(self.name))
    return faits


def _operation(migration, nom):
    for operation in migration.Migration.operations:
        if operation.name == nom:
            return operation
    raise AssertionError(f'operation introuvable : {nom}')


# ── Le cas de la panne : la table est déjà là ─────────────────────────────

def test_une_table_deja_la_n_est_pas_recreee(migration, appels):
    """Exactement l'état trouvé sur la machine. C'est le 1050."""
    operation = _operation(migration, 'SavedWatchConfiguration')
    editeur = _FauxEditeur({'ecommerce_savedwatchconfiguration'})

    operation.database_forwards('ecommerce', editeur, _FauxEtat(), _FauxEtat())

    assert appels['avant'] == []


def test_une_table_absente_est_bien_creee(migration, appels):
    """Le cas normal ne doit pas être abîmé par le correctif."""
    operation = _operation(migration, 'SavedWatchConfiguration')
    editeur = _FauxEditeur(set())

    operation.database_forwards('ecommerce', editeur, _FauxEtat(), _FauxEtat())

    assert appels['avant'] == ['SavedWatchConfiguration']


def test_chaque_operation_decide_pour_sa_propre_table(migration, appels):
    """L'état de production : une table sur trois. Les deux autres passent."""
    editeur = _FauxEditeur({'ecommerce_savedwatchconfiguration'})

    for operation in migration.Migration.operations:
        operation.database_forwards('ecommerce', editeur,
                                    _FauxEtat(), _FauxEtat())

    assert appels['avant'] == ['WatchPreset', 'WatchCustomizationOption']


def test_les_tables_des_autres_apps_ne_changent_rien(migration, appels):
    """Le constat porte sur la table de l'opération, pas sur la base."""
    editeur = _FauxEditeur({'btp_btpproject', 'core_company', 'auth_user'})

    for operation in migration.Migration.operations:
        operation.database_forwards('ecommerce', editeur,
                                    _FauxEtat(), _FauxEtat())

    assert appels['avant'] == list(MODELES)


# ── L'annulation doit être tolérante elle aussi ───────────────────────────

def test_l_annulation_ignore_une_table_deja_absente(migration, appels):
    """Sinon le même piège se referme dans l'autre sens."""
    editeur = _FauxEditeur({'ecommerce_watchpreset'})

    for operation in migration.Migration.operations:
        operation.database_backwards('ecommerce', editeur,
                                     _FauxEtat(), _FauxEtat())

    assert appels['arriere'] == ['WatchPreset']


def test_l_annulation_supprime_les_tables_presentes(migration, appels):
    editeur = _FauxEditeur(set(TABLES))

    for operation in migration.Migration.operations:
        operation.database_backwards('ecommerce', editeur,
                                     _FauxEtat(), _FauxEtat())

    assert appels['arriere'] == list(MODELES)


# ── La forme, pour qu'on ne la « simplifie » pas ──────────────────────────

def test_les_trois_operations_sont_conditionnelles(migration):
    """Un retour à des CreateModel nus rouvrirait le défaut."""
    operations = migration.Migration.operations

    assert len(operations) == 3
    assert [o.name for o in operations] == list(MODELES)
    for operation in operations:
        assert isinstance(operation, migration.CreerLaTableSiAbsente), (
            f'{operation.name} doit être conditionnelle')
        # Et rester un CreateModel : c'est lui qui porte l'état.
        assert isinstance(operation, m.CreateModel)


def test_l_etat_reste_gere_par_django(migration):
    """`state_forwards` n'est pas redéfini : l'état ne doit pas diverger.

    C'est ce qui garantit que `makemigrations --check` ne détecte rien.
    """
    assert (migration.CreerLaTableSiAbsente.state_forwards
            is m.CreateModel.state_forwards)


def test_les_noms_des_tables_restent_ceux_attendus():
    """Si un db_table changeait, les listes de ce fichier mentiraient."""
    from django.apps import apps

    reels = tuple(
        apps.get_model('ecommerce', nom)._meta.db_table for nom in MODELES)

    assert reels == TABLES
