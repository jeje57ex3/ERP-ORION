"""Le pointage chantier référence désormais un compte utilisateur.

`BTPTimesheet.employee` pointait vers `hr.Employee`, le modèle vise maintenant
`AUTH_USER_MODEL`. Django en déduit tout seul un `MODIFY employee_id integer`
suivi d'une nouvelle contrainte vers `auth_user` — et c'est exactement ce qu'il
ne faut PAS exécuter tel quel : les identifiants déjà en base sont des clés
d'`hr_employee`, qui seraient alors relues comme des clés d'`auth_user`. Chaque
pointage se retrouverait attribué à un utilisateur arbitraire, sans erreur,
sans trace, et sans qu'aucun écran ne le signale.

La conversion est possible parce qu'`Employee.user` existe : l'identifiant
d'employé se traduit en identifiant d'utilisateur. Mais ce lien est
`null=True` — un employé sans compte n'a pas de traduction. Pour ces lignes,
il n'y a aucune bonne réponse automatique : les supprimer détruirait des
heures pointées, les laisser corromprait l'attribution. La migration
s'interrompt donc en nommant les employés concernés, et laisse la décision à
l'exploitant.

Vérifié sur la base de développement : `btp_btptimesheet` y est vide, la
conversion n'y change donc rien. C'est sur un serveur en production que ce
garde-fou compte.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def traduire_employes_en_utilisateurs(apps, schema_editor):
    """Remplace chaque identifiant d'employé par celui de son compte."""
    Timesheet = apps.get_model('btp', 'BTPTimesheet')
    Employee = apps.get_model('hr', 'Employee')

    if not Timesheet.objects.exists():
        return

    # Les identifiants présents dans la colonne sont ceux d'hr_employee.
    employes_references = set(
        Timesheet.objects.values_list('employee_id', flat=True).distinct()
    )
    comptes = dict(
        Employee.objects
        .filter(id__in=employes_references)
        .values_list('id', 'user_id')
    )

    # Un employé sans compte utilisateur, ou un identifiant qui ne correspond
    # à aucun employé : aucune traduction possible.
    sans_traduction = sorted(
        identifiant for identifiant in employes_references
        if not comptes.get(identifiant)
    )
    if sans_traduction:
        details = []
        for identifiant in sans_traduction[:10]:
            employe = Employee.objects.filter(id=identifiant).first()
            nombre = Timesheet.objects.filter(employee_id=identifiant).count()
            if employe is None:
                details.append(
                    "  - employé introuvable (id %s) : %s pointage(s)"
                    % (identifiant, nombre)
                )
            else:
                details.append(
                    "  - %s %s (id %s) n'a pas de compte utilisateur : "
                    "%s pointage(s)"
                    % (employe.first_name, employe.last_name, identifiant,
                       nombre)
                )
        if len(sans_traduction) > 10:
            details.append(
                '  - ... et %s autre(s)' % (len(sans_traduction) - 10)
            )

        raise RuntimeError(
            'Migration btp.0007 interrompue : le pointage chantier passe '
            "d'une référence employé à une référence compte utilisateur, et "
            "ces employés n'ont pas de compte :\n"
            + '\n'.join(details)
            + "\n\nAucune donnée n'a été modifiée. Deux issues :\n"
            '  1. créer un compte utilisateur pour ces employés et le '
            "rattacher à leur fiche (champ « Compte utilisateur »), puis "
            'relancer la migration ;\n'
            '  2. si ces pointages sont obsolètes, les supprimer '
            'explicitement avant de relancer.\n'
            'Les traduire au hasard attribuerait des heures pointées à '
            "d'autres personnes."
        )

    # Traduction effective, par employé pour rester lisible dans les journaux.
    for identifiant_employe, identifiant_compte in comptes.items():
        Timesheet.objects.filter(employee_id=identifiant_employe).update(
            employee_id=identifiant_compte,
        )


def retraduire_utilisateurs_en_employes(apps, schema_editor):
    """Retour arrière : du compte utilisateur vers la fiche employé."""
    Timesheet = apps.get_model('btp', 'BTPTimesheet')
    Employee = apps.get_model('hr', 'Employee')

    if not Timesheet.objects.exists():
        return

    comptes_references = set(
        Timesheet.objects.values_list('employee_id', flat=True).distinct()
    )
    fiches = dict(
        Employee.objects
        .filter(user_id__in=comptes_references)
        .values_list('user_id', 'id')
    )
    manquants = sorted(
        identifiant for identifiant in comptes_references
        if identifiant not in fiches
    )
    if manquants:
        raise RuntimeError(
            'Retour arrière de btp.0007 impossible : %s compte(s) '
            "utilisateur n'ont pas de fiche employé (ids : %s). Les "
            'pointages correspondants ne peuvent pas être réattribués sans '
            'décision.' % (len(manquants), ', '.join(map(str, manquants)))
        )

    for identifiant_compte, identifiant_employe in fiches.items():
        Timesheet.objects.filter(employee_id=identifiant_compte).update(
            employee_id=identifiant_employe,
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('btp', '0006_guidedquoteestimate_travel_distance_km_and_more'),
        # hr.Employee est lu par la traduction ci-dessus : sa table doit
        # exister, et porter son champ « user ».
        ('hr', '0001_initial'),
    ]

    operations = [
        # La traduction vient AVANT la contrainte : une fois la clé étrangère
        # repointée vers auth_user, les anciens identifiants d'employés y
        # seraient déjà invalides (ou, pire, valides mais faux).
        migrations.RunPython(
            traduire_employes_en_utilisateurs,
            retraduire_utilisateurs_en_employes,
        ),
        migrations.AlterField(
            model_name='btptimesheet',
            name='employee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='btp_timesheets', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='electricitypricelibrary',
            name='product_family',
            field=models.CharField(blank=True, default='', help_text='Regroupe plusieurs gammes du même équipement (ex: "Prise / interrupteur") dans le configurateur public. Laisser vide si ce poste n\'a qu\'une seule gamme.', max_length=100, verbose_name='Famille de produit'),
        ),
    ]
