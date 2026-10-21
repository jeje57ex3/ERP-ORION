"""Compétences et habilitations des salariés.

Le système existait déjà — deux modèles, sept vues, cinq gabarits — et
n'avait **aucun test**. Ce fichier en pose, et couvre les quatre défauts
corrigés avec lui.

**Le scan était inaccessible en production.** Le gabarit pointait vers
`cert.file.url`, soit `/media/employee_certifications/…`, et personne ne
sert `/media/` : le `static(MEDIA_URL)` d'`erp_btp/urls.py` est derrière
`if settings.DEBUG`, nginx proxifie `/media/` vers gunicorn au lieu de
servir le disque, et WhiteNoise ne sert que `STATIC_ROOT`. L'envoi
fonctionnait, le trombone s'affichait, le clic rendait 404.

**Et le correctif facile aurait été pire.** Ajouter un `location /media/`
servant le disque rendait tous les scans de CACES lisibles par quiconque
devine l'URL. D'où une vue qui vérifie *qui* demande — contrairement à
`private_document_download`, dans le même module, qui ne contrôle que
l'entreprise et laisse donc n'importe quel collègue télécharger le document
privé d'un autre.

**Rien ne remontait les échéances.** `is_expired` et `expires_soon`
existaient mais ne coloraient qu'une ligne sur la fiche d'un salarié. Pour
un CACES, le besoin est l'inverse : le savoir avant que la personne arrive
sur chantier.

**Un « Responsable RH » ne pouvait rien saisir.** Le rôle `hr_manager`
existe dans `ROLE_CHOICES` et était exclu d'`_is_hr_admin` — il fallait
donner les droits d'administration générale à qui n'avait besoin que des
siens.
"""

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.hr.certification_service import (
    certifications_a_surveiller,
    compter_par_statut,
    peut_voir_certification,
    statut_echeance,
)
from apps.hr.models import Employee, EmployeeCertification, EmployeeSkill

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


def creer_compte(nom, role='user', company=None, superuser=False):
    utilisateur = User.objects.create_user(
        username=nom, password='x', is_superuser=superuser,
        is_staff=superuser)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    if company is not None:
        profil.companies.add(company)
    # Relecture : le signal qui crée le profil le met en cache sur l'objet
    # User avec son rôle d'origine.
    return User.objects.get(pk=utilisateur.pk)


def creer_salarie(company, prenom='Marc', nom='Dupont', avec_compte=True,
                  actif=True):
    utilisateur = creer_compte(f'{prenom}.{nom}'.lower(), company=company) \
        if avec_compte else None
    return Employee.objects.create(
        company=company, first_name=prenom, last_name=nom,
        user=utilisateur, is_active=actif)


def creer_habilitation(salarie, nom='CACES R482', jours=None, actif=True,
                       categorie='caces', avec_fichier=False):
    """jours : décalage par rapport à aujourd'hui. None = pas d'expiration."""
    expiration = None if jours is None else date.today() + timedelta(days=jours)
    certification = EmployeeCertification(
        employee=salarie, category=categorie, name=nom,
        expiry_date=expiration, is_active=actif)
    if avec_fichier:
        certification.file = SimpleUploadedFile(
            'caces.pdf', b'%PDF-1.4 contenu de test',
            content_type='application/pdf')
    certification.save()
    return certification


@pytest.fixture
def salarie(entreprise):
    return creer_salarie(entreprise)


@pytest.fixture
def rh(entreprise):
    """Un responsable RH, et non un administrateur : c'est le cas corrigé."""
    return creer_compte('drh', role='hr_manager', company=entreprise)


@pytest.fixture
def admin(entreprise):
    return creer_compte('patron', role='admin', company=entreprise)


# ── 1. Les compétences, qui fonctionnaient déjà ─────────────────────────────

def test_ajouter_une_competence(client, admin, salarie):
    client.force_login(admin)
    reponse = client.post(
        reverse('hr:skill_create', args=[salarie.pk]),
        {'name': 'Soudure TIG', 'level': 'expert'})
    assert reponse.status_code in (301, 302)
    competence = EmployeeSkill.objects.get(employee=salarie)
    assert competence.name == 'Soudure TIG'
    assert competence.level == 'expert'


def test_une_competence_d_une_autre_entreprise_est_introuvable(
        client, admin, autre_entreprise):
    """404 et non 403 : l'existence du salarié ne doit pas se déduire."""
    etranger = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    competence = EmployeeSkill.objects.create(
        employee=etranger, name='Secret', level='expert')
    client.force_login(admin)
    assert client.get(reverse('hr:skill_edit',
                              args=[competence.pk])).status_code == 404


def test_un_utilisateur_ordinaire_ne_saisit_pas_de_competence(
        client, entreprise, salarie):
    simple = creer_compte('ouvrier', role='user', company=entreprise)
    client.force_login(simple)
    client.post(reverse('hr:skill_create', args=[salarie.pk]),
                {'name': 'Rien', 'level': 'expert'})
    assert not EmployeeSkill.objects.filter(employee=salarie).exists()


# ── 2. Le responsable RH, enfin autorisé ────────────────────────────────────

def test_un_responsable_rh_peut_saisir_une_competence(client, rh, salarie):
    """Le défaut corrigé : le rôle fait pour ça en était exclu.

    Il fallait donner les droits d'administration générale à qui n'avait
    besoin que des siens — ce qui est la façon la plus sûre de les voir se
    répandre.
    """
    client.force_login(rh)
    client.post(reverse('hr:skill_create', args=[salarie.pk]),
                {'name': 'Habilitation B1V', 'level': 'intermediate'})
    assert EmployeeSkill.objects.filter(employee=salarie).exists()


def test_un_responsable_rh_peut_enregistrer_une_habilitation(client, rh,
                                                              salarie):
    client.force_login(rh)
    client.post(reverse('hr:certification_create', args=[salarie.pk]), {
        'category': 'caces', 'name': 'CACES R489',
        'expiry_date': '2027-06-30', 'is_active': 'on'})
    assert EmployeeCertification.objects.filter(employee=salarie).exists()


def test_un_responsable_rh_voit_l_ecran_des_echeances(client, rh, salarie):
    creer_habilitation(salarie, jours=10)
    client.force_login(rh)
    reponse = client.get(reverse('hr:certification_expiring'))
    assert reponse.status_code == 200


def test_un_salarie_ordinaire_ne_voit_pas_l_ecran_des_echeances(
        client, entreprise, salarie):
    """Il liste les habilitations de tout le monde."""
    simple = creer_compte('ouvrier', role='user', company=entreprise)
    client.force_login(simple)
    reponse = client.get(reverse('hr:certification_expiring'), follow=True)
    # Le PREMIER saut, et non le dernier : « mes competences » redirige a
    # son tour quand le compte n'a pas de fiche salarie, et la chaine finit
    # sur le tableau de bord. Verifier la fin testerait cette seconde
    # redirection, pas le refus qui nous interesse.
    premier_saut = reponse.redirect_chain[0][0]
    assert reverse('hr:my_skills_certifications') in premier_saut


# ── 3. Les échéances ────────────────────────────────────────────────────────

@pytest.mark.parametrize('jours,attendu', [
    (-1, 'expiree'), (-400, 'expiree'),
    (0, 'imminente'), (1, 'imminente'), (30, 'imminente'),
    (31, 'proche'), (90, 'proche'),
    (91, None), (3650, None),
    (None, None),
])
def test_statut_d_echeance(jours, attendu, salarie):
    """Les seuils, y compris leurs bords.

    `None` recouvre deux cas très différents et c'est voulu : une échéance
    lointaine, et une habilitation SANS expiration — un diplôme ne périme
    pas. Les distinguer obligerait chaque appelant à traiter un troisième
    cas pour rien.
    """
    certification = creer_habilitation(salarie, jours=jours)
    assert statut_echeance(certification) == attendu


def test_un_diplome_sans_expiration_ne_remonte_jamais(entreprise, salarie):
    creer_habilitation(salarie, nom='BTS Électrotechnique', jours=None,
                       categorie='diploma')
    assert certifications_a_surveiller(entreprise) == []


def test_les_expirees_passent_devant(entreprise, salarie):
    """L'ordre d'affichage est l'ordre d'urgence.

    Trier sur la seule date mettrait les expirées en tête de toute façon,
    mais l'ordre deviendrait faux dès qu'on filtre les expirées.
    """
    creer_habilitation(salarie, nom='Proche', jours=80)
    creer_habilitation(salarie, nom='Imminente', jours=10)
    creer_habilitation(salarie, nom='Expiree', jours=-5)

    noms = [ligne['certification'].name
            for ligne in certifications_a_surveiller(entreprise)]
    assert noms == ['Expiree', 'Imminente', 'Proche']


def test_une_habilitation_desactivee_est_exclue(entreprise, salarie):
    """Elle a été remplacée ou retirée : la signaler remettrait du bruit."""
    creer_habilitation(salarie, nom='Retiree', jours=-5, actif=False)
    assert certifications_a_surveiller(entreprise) == []


def test_l_habilitation_d_un_salarie_parti_est_exclue(entreprise):
    """Ce n'est pas un risque, c'est de l'archive.

    La laisser remonter ferait grossir la liste jusqu'à ce qu'on cesse de
    la lire — et c'est exactement ce qui rend un écran d'alerte inutile.
    """
    parti = creer_salarie(entreprise, 'Jean', 'Parti', actif=False)
    creer_habilitation(parti, nom='CACES perime', jours=-30)
    assert certifications_a_surveiller(entreprise) == []


def test_les_habilitations_d_une_autre_entreprise_sont_exclues(
        entreprise, autre_entreprise):
    interne = creer_salarie(entreprise, 'Marc', 'Interne')
    externe = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    creer_habilitation(interne, nom='A nous', jours=10)
    creer_habilitation(externe, nom='Aux autres', jours=10)

    noms = [ligne['certification'].name
            for ligne in certifications_a_surveiller(entreprise)]
    assert noms == ['A nous']


def test_les_compteurs_decrivent_la_liste_affichee(entreprise, salarie):
    """Sinon l'en-tête annonce « 4 expirées » au-dessus d'un tableau qui en
    montre 3, et on cesse de croire les deux."""
    creer_habilitation(salarie, nom='E1', jours=-5)
    creer_habilitation(salarie, nom='E2', jours=-50)
    creer_habilitation(salarie, nom='I1', jours=10)
    creer_habilitation(salarie, nom='P1', jours=80)

    lignes = certifications_a_surveiller(entreprise)
    compteurs = compter_par_statut(lignes)
    assert compteurs == {'expiree': 2, 'imminente': 1, 'proche': 1,
                         'total': 4}
    assert compteurs['total'] == len(lignes)


def test_l_horizon_resserre_exclut_les_lointaines_mais_pas_les_expirees(
        entreprise, salarie):
    """Une habilitation déjà expirée reste affichée quel que soit l'horizon.

    La masquer parce qu'elle est « hors fenêtre » serait absurde : c'est la
    plus urgente.
    """
    creer_habilitation(salarie, nom='Expiree', jours=-5)
    creer_habilitation(salarie, nom='Proche', jours=80)

    noms = [ligne['certification'].name
            for ligne in certifications_a_surveiller(entreprise, jours=30)]
    assert noms == ['Expiree']


@pytest.mark.parametrize('valeur', ['abc', '-10', '100000', ''])
def test_un_horizon_de_travers_ne_casse_pas_la_page(client, rh, salarie,
                                                     valeur):
    creer_habilitation(salarie, jours=10)
    client.force_login(rh)
    reponse = client.get(reverse('hr:certification_expiring'),
                         {'jours': valeur})
    assert reponse.status_code == 200
    assert 0 <= reponse.context['jours'] <= 365


def test_l_ecran_affiche_l_habilitation_expiree(client, rh, salarie):
    creer_habilitation(salarie, nom='CACES R482', jours=-3)
    client.force_login(rh)
    corps = client.get(reverse('hr:certification_expiring')).content.decode()
    assert 'CACES R482' in corps
    assert salarie.full_name in corps
    assert 'Expirée' in corps


# ── 4. Le téléchargement du scan ────────────────────────────────────────────

def test_le_scan_se_telecharge(client, rh, salarie):
    """Le défaut principal : ce lien rendait 404 en production.

    Rien ne sert /media/ hors DEBUG — ni Django, ni nginx, ni WhiteNoise.
    """
    certification = creer_habilitation(salarie, avec_fichier=True)
    client.force_login(rh)
    reponse = client.get(reverse('hr:certification_download',
                                 args=[certification.pk]))
    assert reponse.status_code == 200
    assert b'%PDF' in b''.join(reponse.streaming_content)


def test_le_telechargement_est_journalise(client, rh, salarie):
    """Un scan de CACES est un document personnel : on sait qui l'a ouvert.

    EmployeeDocumentAccessLog est attaché à EmployeePrivateDocument par clé
    étrangère et ne peut pas accueillir une certification sans changement
    de schéma ; AuditLog porte déjà ce qu'il faut.
    """
    from apps.core.models import AuditLog
    certification = creer_habilitation(salarie, avec_fichier=True)
    client.force_login(rh)
    client.get(reverse('hr:certification_download', args=[certification.pk]))

    entree = AuditLog.objects.filter(
        action='download', model_name='EmployeeCertification',
        object_id=str(certification.pk)).first()
    assert entree is not None
    assert entree.user == rh


def test_le_salarie_telecharge_son_propre_scan(client, entreprise):
    """Il n'a aucun droit RH, et c'est son document."""
    salarie = creer_salarie(entreprise, 'Marc', 'Dupont')
    certification = creer_habilitation(salarie, avec_fichier=True)
    client.force_login(salarie.user)
    reponse = client.get(reverse('hr:certification_download',
                                 args=[certification.pk]))
    assert reponse.status_code == 200


def test_un_collegue_ne_telecharge_pas_le_scan_d_un_autre(client, entreprise):
    """Le défaut que `private_document_download` porte encore.

    Celui-ci ne vérifie que l'entreprise : n'importe quel compte connecté y
    télécharge le document privé de n'importe quel collègue. Ce contrôle-ci
    est plus serré, et le test l'épingle pour qu'il le reste.
    """
    salarie = creer_salarie(entreprise, 'Marc', 'Dupont')
    certification = creer_habilitation(salarie, avec_fichier=True)
    collegue = creer_compte('autre.ouvrier', role='user', company=entreprise)

    client.force_login(collegue)
    reponse = client.get(reverse('hr:certification_download',
                                 args=[certification.pk]))
    assert reponse.status_code == 404


def test_le_scan_d_une_autre_entreprise_est_introuvable(client, rh,
                                                         autre_entreprise):
    etranger = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    certification = creer_habilitation(etranger, avec_fichier=True)
    client.force_login(rh)
    assert client.get(reverse('hr:certification_download',
                              args=[certification.pk])).status_code == 404


def test_une_habilitation_sans_document_ne_rend_pas_404(client, rh, salarie):
    """Elle redirige en l'expliquant : un 404 laisserait croire à une panne."""
    certification = creer_habilitation(salarie, avec_fichier=False)
    client.force_login(rh)
    reponse = client.get(reverse('hr:certification_download',
                                 args=[certification.pk]), follow=True)
    assert reponse.status_code == 200
    assert 'Aucun document joint' in reponse.content.decode()


def test_un_fichier_disparu_du_disque_est_explique(client, rh, salarie):
    """Restauration partielle, media non sauvegardé : ça arrive.

    « Il a été perdu, pas supprimé » oriente vers la sauvegarde ; un 404
    muet laisse chercher dans l'ERP.
    """
    import os
    certification = creer_habilitation(salarie, avec_fichier=True)
    os.remove(certification.file.path)

    client.force_login(rh)
    reponse = client.get(reverse('hr:certification_download',
                                 args=[certification.pk]), follow=True)
    assert reponse.status_code == 200
    assert 'introuvable sur le serveur' in reponse.content.decode()


def test_un_anonyme_ne_telecharge_rien(client, salarie):
    certification = creer_habilitation(salarie, avec_fichier=True)
    reponse = client.get(reverse('hr:certification_download',
                                 args=[certification.pk]))
    assert reponse.status_code in (301, 302)


def test_peut_voir_certification_refuse_une_autre_entreprise(
        entreprise, autre_entreprise):
    """Contrôle unitaire, hors requête : la règle doit tenir seule."""
    etranger = creer_salarie(autre_entreprise, 'Paul', 'Externe')
    certification = creer_habilitation(etranger)
    patron = creer_compte('root', role='superadmin', company=entreprise,
                          superuser=True)
    assert peut_voir_certification(patron, certification, entreprise) is False


# ── 5. Le widget ────────────────────────────────────────────────────────────

def test_le_widget_lit_la_meme_selection_que_l_ecran(entreprise, salarie, rh):
    """Deux définitions de « à surveiller » auraient divergé.

    Le widget annoncerait alors un nombre que l'écran ne confirme pas, et
    on apprendrait à ne plus regarder ni l'un ni l'autre.
    """
    from apps.dashboard.widgets import get_hr_expiring_certifications_data

    creer_habilitation(salarie, nom='E1', jours=-5)
    creer_habilitation(salarie, nom='I1', jours=10)
    creer_habilitation(salarie, nom='Lointaine', jours=200)

    donnees = get_hr_expiring_certifications_data(rh, entreprise)
    attendu = certifications_a_surveiller(entreprise)

    assert donnees['total'] == len(attendu) == 2
    assert donnees['compteurs'] == compter_par_statut(attendu)
    assert [l['certification'].name for l in donnees['lignes']] == ['E1', 'I1']


def test_le_widget_ne_leve_jamais(entreprise, rh, monkeypatch):
    """Un widget qui lève casse le tableau de bord entier.

    _safe l'enveloppe ; ce test vérifie que l'enveloppe est bien là, parce
    qu'un widget ajouté sans elle ne se remarque qu'en production.
    """
    from apps.dashboard import widgets

    def explose(*args, **kwargs):
        raise RuntimeError('base injoignable')

    monkeypatch.setattr(
        'apps.hr.certification_service.certifications_a_surveiller', explose)
    donnees = widgets.get_hr_expiring_certifications_data(rh, entreprise)
    assert donnees == {'lignes': [], 'compteurs': {}, 'total': 0}


def test_le_widget_est_au_catalogue():
    """Sans entrée au catalogue, la fonction existe et personne ne la voit."""
    from apps.dashboard.management.commands.seed_dashboard_widgets import (
        WIDGETS,
    )
    codes = {widget['code'] for widget in WIDGETS}
    assert 'hr_expiring_certifications' in codes


def test_le_widget_est_branche_sur_sa_fonction():
    """Le chaînon qui manquerait sans bruit.

    Au catalogue mais pas au registre, le widget s'affiche vide pour
    toujours : `widget_data[code]` n'existe pas, le gabarit tombe sur son
    état vide, et rien n'indique que c'est un oubli de câblage plutôt
    qu'une absence de données.

    Le registre `LOADERS` est un dictionnaire LOCAL à
    `get_dashboard_context` : il n'est pas importable, et lire la source
    est le seul moyen d'en vérifier le contenu. C'est assumé — l'alternative
    serait de ne pas le vérifier.
    """
    import inspect

    from apps.dashboard.services import get_dashboard_context

    source = inspect.getsource(get_dashboard_context)
    assert "'hr_expiring_certifications'" in source
    assert 'get_hr_expiring_certifications_data' in source
