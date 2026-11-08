# -*- coding: utf-8 -*-
"""Une migration interrompue ne doit pas condamner toutes les suivantes.

CE QUI EST ARRIVÉ SUR L'APPLIANCE, deux fois en quinze jours. MySQL n'a pas
de DDL transactionnelle : une migration interrompue laisse derrière elle les
tables et les colonnes qu'elle venait de créer, sans écrire sa ligne dans
`django_migrations`. Django la croit encore à faire, la rejoue depuis le
début, et MySQL répond :

    (1050, "Table 'ecommerce_savedwatchconfiguration' already exists")
    (1060, "Duplicate column name 'archive_ref'")

L'état est ABSORBANT : chaque tentative échoue à l'identique. Et comme
`manage.py migrate` sans argument traite les 87 apps, UNE migration bloquée
bloque TOUTES les mises à jour de l'ERP — y compris celle qui apporte le
correctif. Ce n'est donc pas un défaut d'`ecommerce` ni de `websites`, c'est
un défaut qui paralyse l'ERP entier.

LE TEST QUI COMPTE LE PLUS N'EST PAS DANS CE FICHIER : c'est la suite
entière, qui applique les VRAIES migrations sur une base neuve. Une
migration cassée fait échouer tous les tests dès la création de la base,
et c'est ainsi qu'une première version du correctif précédent a été prise
en défaut.

Les tests ci-dessous pincent ce que la suite ne voit jamais : le
comportement quand la table ou la colonne existe DÉJÀ — le cas de
production exactement, qu'une base neuve ne reproduit pas.
"""

import importlib
import types

import pytest
from django.apps import apps
from django.db import migrations as m
from django.db import models

from apps.core import migrations_rejouables as rejouables

MODULE_0027 = ('apps.websites.migrations.'
               '0027_alter_storeproductimage_options_and_more')

TABLE_PRODUIT = 'websites_storeproduct'


# ─── Un schema_editor réduit à ce que les opérations lui demandent ──────────

class _FauxCurseur:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FauxEditeur:
    def __init__(self, tables=(), colonnes=None):
        self.colonnes = dict(colonnes or {})
        self.tables_consultees = []
        self.connection = types.SimpleNamespace(
            alias='default',
            cursor=lambda: _FauxCurseur(),
            introspection=types.SimpleNamespace(
                table_names=lambda: list(tables),
                get_table_description=self._description))

    def _description(self, curseur, table):
        self.tables_consultees.append(table)
        return [types.SimpleNamespace(name=nom)
                for nom in self.colonnes.get(table, ())]


class _FauxEtat:
    """Le registre réel suffit : les modèles visés y sont déclarés."""
    apps = apps


@pytest.fixture
def poses(monkeypatch):
    """Intercepte l'appel aux opérations Django parentes.

    On n'exécute pas le vrai `add_field` : il passerait par les routeurs de
    base de ce projet, qui en comptent plusieurs, et le test mesurerait
    alors leur avis plutôt que la décision testée ici.
    """
    faits = {'champs': [], 'champs_retires': [],
             'tables': [], 'tables_retirees': []}
    monkeypatch.setattr(m.AddField, 'database_forwards',
                        lambda self, *a, **k: faits['champs'].append(self.name))
    monkeypatch.setattr(
        m.AddField, 'database_backwards',
        lambda self, *a, **k: faits['champs_retires'].append(self.name))
    monkeypatch.setattr(m.CreateModel, 'database_forwards',
                        lambda self, *a, **k: faits['tables'].append(self.name))
    monkeypatch.setattr(
        m.CreateModel, 'database_backwards',
        lambda self, *a, **k: faits['tables_retirees'].append(self.name))
    return faits


def _ajout(nom_du_champ, modele='storeproduct'):
    return rejouables.AjouterLeChampSiAbsent(
        model_name=modele, name=nom_du_champ,
        field=models.CharField(blank=True, max_length=120))


def _executer(operation, editeur):
    operation.database_forwards('websites', editeur, _FauxEtat(), _FauxEtat())


# ─── Le cas de production : la colonne est déjà là ─────────────────────────

def test_la_colonne_deja_presente_n_est_pas_reajoutee(poses):
    """Le 1060 exact relevé sur l'appliance."""
    editeur = _FauxEditeur(tables=[TABLE_PRODUIT],
                           colonnes={TABLE_PRODUIT: ['id', 'archive_ref']})
    _executer(_ajout('archive_ref'), editeur)
    assert poses['champs'] == []


def test_la_colonne_absente_est_bien_posee(poses):
    editeur = _FauxEditeur(tables=[TABLE_PRODUIT],
                           colonnes={TABLE_PRODUIT: ['id']})
    _executer(_ajout('archive_ref'), editeur)
    assert poses['champs'] == ['archive_ref']


def test_une_seule_colonne_presente_les_autres_sont_posees(poses):
    """Le cas réel : on ne sait pas combien des 27 avaient été posées.

    C'est pour cela que la tolérance est par CHAMP et non par migration.
    """
    editeur = _FauxEditeur(
        tables=[TABLE_PRODUIT],
        colonnes={TABLE_PRODUIT: ['id', 'archive_ref', 'dimensions']})
    for nom in ('archive_ref', 'care_instructions', 'condition',
                'dimensions', 'materials'):
        _executer(_ajout(nom), editeur)
    assert poses['champs'] == ['care_instructions', 'condition', 'materials']


def test_table_absente_l_erreur_reste_celle_de_django(poses):
    """Sans la table, ce n'est pas à nous de masquer le problème.

    On délègue, et Django produit son erreur, qui nomme la vraie cause.
    """
    editeur = _FauxEditeur(tables=[], colonnes={})
    _executer(_ajout('archive_ref'), editeur)
    assert poses['champs'] == ['archive_ref']
    assert editeur.tables_consultees == [], (
        'aucune introspection de colonnes ne doit etre tentee sur une table '
        'absente : elle leverait une erreur technique a la place du vrai '
        'message')


def test_un_manytomany_est_delegue_sans_etre_teste_de_travers():
    """Un M2M vit dans une table de liaison, pas dans une colonne."""
    operation = rejouables.AjouterLeChampSiAbsent(
        model_name='userprofile', name='companies', field=None)
    modele = apps.get_model('accounts', 'UserProfile')
    assert operation._colonne_ou_rien(modele) is None
    editeur = _FauxEditeur(tables=['accounts_userprofile'],
                           colonnes={'accounts_userprofile': ['id']})
    assert operation._la_colonne_est_la(editeur, modele) is False


# ─── Le retour en arrière, par symétrie ────────────────────────────────────

def test_retirer_une_colonne_absente_ne_fait_rien(poses):
    editeur = _FauxEditeur(tables=[TABLE_PRODUIT],
                           colonnes={TABLE_PRODUIT: ['id']})
    _ajout('archive_ref').database_backwards(
        'websites', editeur, _FauxEtat(), _FauxEtat())
    assert poses['champs_retires'] == []


def test_retirer_une_colonne_presente_est_delegue(poses):
    editeur = _FauxEditeur(tables=[TABLE_PRODUIT],
                           colonnes={TABLE_PRODUIT: ['id', 'archive_ref']})
    _ajout('archive_ref').database_backwards(
        'websites', editeur, _FauxEtat(), _FauxEtat())
    assert poses['champs_retires'] == ['archive_ref']


# ─── Les tables, même logique ──────────────────────────────────────────────

def test_la_table_deja_presente_n_est_pas_recreee(poses):
    operation = rejouables.CreerLaTableSiAbsente(
        name='StoreProductVariant', fields=[])
    editeur = _FauxEditeur(tables=['websites_storeproductvariant'])
    operation.database_forwards('websites', editeur, _FauxEtat(), _FauxEtat())
    assert poses['tables'] == []


def test_la_table_absente_est_bien_creee(poses):
    operation = rejouables.CreerLaTableSiAbsente(
        name='StoreProductVariant', fields=[])
    editeur = _FauxEditeur(tables=['websites_storeproduct'])
    operation.database_forwards('websites', editeur, _FauxEtat(), _FauxEtat())
    assert poses['tables'] == ['StoreProductVariant']


# ─── L'état reste à Django, et c'est essentiel ─────────────────────────────

def test_l_etat_n_est_jamais_surcharge():
    """`makemigrations --check` doit continuer de répondre « No changes ».

    Surcharger `state_forwards` ferait diverger l'état des modèles, et
    Django proposerait une migration de rattrapage à chaque lancement.
    """
    assert (rejouables.AjouterLeChampSiAbsent.state_forwards
            is m.AddField.state_forwards)
    assert (rejouables.CreerLaTableSiAbsente.state_forwards
            is m.CreateModel.state_forwards)


# ─── La migration 0027 elle-même ───────────────────────────────────────────

@pytest.fixture
def migration_0027():
    # import_module et non `import` : un nom de module qui commence par un
    # chiffre n'est pas un identifiant Python valide.
    return importlib.import_module(MODULE_0027)


def test_0027_n_a_plus_aucune_operation_nue(migration_0027):
    """Un seul AddField non tolérant suffit à rebloquer tout l'ERP."""
    nues = [type(operation).__name__
            for operation in migration_0027.Migration.operations
            if type(operation) in (m.AddField, m.CreateModel)]
    assert nues == [], 'operations non rejouables dans 0027 : %s' % nues


def test_0027_couvre_bien_toutes_ses_operations_ddl(migration_0027):
    operations = migration_0027.Migration.operations
    champs = [o for o in operations
              if isinstance(o, rejouables.AjouterLeChampSiAbsent)]
    tables = [o for o in operations
              if isinstance(o, rejouables.CreerLaTableSiAbsente)]
    assert len(champs) == 27
    assert len(tables) == 2
    assert 'archive_ref' in [o.name for o in champs]


def test_0027_laisse_les_options_de_modele_a_django(migration_0027):
    """AlterModelOptions ne touche pas la base : rien à rendre tolérant."""
    options = [o for o in migration_0027.Migration.operations
               if isinstance(o, m.AlterModelOptions)]
    assert len(options) == 1


def test_les_champs_de_0027_existent_vraiment_sur_les_modeles(migration_0027):
    """Garde-fou contre une faute de frappe dans un nom de champ.

    Une opération qui nomme un champ inexistant ne lèverait son
    `FieldDoesNotExist` qu'au moment de migrer, donc en production.
    """
    for operation in migration_0027.Migration.operations:
        if not isinstance(operation, rejouables.AjouterLeChampSiAbsent):
            continue
        modele = apps.get_model('websites', operation.model_name)
        champ = modele._meta.get_field(operation.name)
        assert champ.column, (
            'sans colonne : %s.%s' % (operation.model_name, operation.name))
