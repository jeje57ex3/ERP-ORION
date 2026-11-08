"""Operations de migration tolerantes a un schema deja a moitie modifie.

POURQUOI CE MODULE EXISTE

MySQL n'a pas de DDL transactionnelle. Une migration interrompue -- processus
tue faute de memoire, delai depasse, perte de connexion -- laisse donc les
tables et les colonnes qu'elle venait de creer, SANS ecrire sa ligne dans
`django_migrations`. Au lancement suivant, Django la rejoue depuis le debut
et bute sur son propre travail :

    (1050, "Table 'ecommerce_savedwatchconfiguration' already exists")
    (1060, "Duplicate column name 'archive_ref'")

L'etat est ABSORBANT : la migration ne peut plus ni avancer ni etre
reconnue, et comme `manage.py migrate` sans argument traite les 87 apps,
UNE migration bloquee bloque TOUTES les mises a jour de l'ERP. Les deux
erreurs ci-dessus ont ete relevees sur l'appliance a quinze jours
d'intervalle.

CE QUE CE MODULE FAIT

Il rend l'operation rejouable : si l'objet est deja la, on ne le recree pas,
et l'etat Django est enregistre normalement. La migration passe, sa ligne est
ecrite, et les suivantes repartent.

CE QU'IL NE FAIT PAS

Il ne repare pas un schema DIVERGENT : une table presente mais dont les
colonnes ne correspondent pas au modele est ignoree telle quelle, et l'erreur
se manifestera plus tard, a la premiere requete. Ces classes couvrent le cas
reel -- objet cree a l'identique par un passage precedent de CETTE migration
-- pas une base bricolee a la main.

POURQUOI PAS `--fake`

`--fake` marque la migration appliquee sans rien executer. Sur un objet
partiellement cree, il enterre l'ecart au lieu de le combler : les colonnes
manquantes le restent, et plus rien ne le signalera jamais. Ici, ce qui
manque est reellement cree ; seul ce qui existe deja est saute.

POURQUOI PAS `SeparateDatabaseAndState`

Essaye, mesure, abandonne : 2644 erreurs sur la suite de tests.
`database_forwards` y recoit l'etat d'AVANT `state_operations` (le
commentaire de Django dit lui-meme « our state functions aren't useful »),
donc un `RunPython` place la ne peut pas resoudre le modele qu'il doit
creer -- `LookupError: App 'ecommerce' doesn't have a ... model`. Heriter de
`CreateModel` / `AddField` resout ce probleme : leurs `database_forwards`
lisent `to_state.apps`, qui contient bien le modele.

L'etat (`state_forwards`) n'est JAMAIS surcharge : c'est Django qui le tient,
et `makemigrations --check` continue donc de repondre « No changes detected ».
"""

from django.db import migrations


def tables_existantes(schema_editor):
    """Noms des tables reellement presentes sur la connexion visee."""
    return set(schema_editor.connection.introspection.table_names())


def colonnes_existantes(schema_editor, table):
    """Noms des colonnes reellement presentes dans `table`."""
    introspection = schema_editor.connection.introspection
    with schema_editor.connection.cursor() as curseur:
        description = introspection.get_table_description(curseur, table)
    return {colonne.name for colonne in description}


class CreerLaTableSiAbsente(migrations.CreateModel):
    """`CreateModel` qui ne recree pas une table deja presente."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modele = to_state.apps.get_model(app_label, self.name)
        if modele._meta.db_table in tables_existantes(schema_editor):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        modele = from_state.apps.get_model(app_label, self.name)
        if modele._meta.db_table not in tables_existantes(schema_editor):
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


class AjouterLeChampSiAbsent(migrations.AddField):
    """`AddField` qui ne reajoute pas une colonne deja presente.

    Ne couvre que les champs portes par une COLONNE. Un ManyToMany est
    materialise par une table de liaison, pas par une colonne : il est
    delegue tel quel a Django, qui sait le faire, plutot que teste de
    travers ici.
    """

    def _colonne_ou_rien(self, modele):
        champ = modele._meta.get_field(self.name)
        if getattr(champ, 'many_to_many', False):
            return None
        return getattr(champ, 'column', None)

    def _la_colonne_est_la(self, schema_editor, modele):
        colonne = self._colonne_ou_rien(modele)
        if not colonne:
            return False
        table = modele._meta.db_table
        # Table absente : la question de la colonne ne se pose pas, et c'est
        # a Django de produire la vraie erreur plutot qu'a nous de la masquer.
        if table not in tables_existantes(schema_editor):
            return False
        return colonne in colonnes_existantes(schema_editor, table)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        modele = to_state.apps.get_model(app_label, self.model_name)
        if self._la_colonne_est_la(schema_editor, modele):
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        modele = from_state.apps.get_model(app_label, self.model_name)
        if not self._la_colonne_est_la(schema_editor, modele):
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)
