"""Dossiers privés salariés : qui peut lire quoi.

Les documents de `EmployeePrivateDocument` sont les plus sensibles de
l'ERP — contrat, bulletin de paie, pièce d'identité, RIB, visite médicale,
sanction disciplinaire. Le modèle portait déjà de quoi les protéger, un
`confidentiality_level` à cinq niveaux et un `visible_to_employee`, et
**aucune vue ne les lisait**.

Les six vues de `dossiers-prives/` ne vérifiaient que l'entreprise. Dans
une société de vingt salariés, les vingt pouvaient lister les dossiers de
tous, ouvrir le journal de qui avait lu quoi, télécharger le bulletin de
paie du voisin, déposer une pièce dans son dossier et supprimer la sienne.
Le contrôle d'entreprise arrête le client d'une autre société, pas le
collègue du bureau d'à côté.

L'ironie du défaut : `my_private_documents` filtrait soigneusement sur
`visible_to_employee`, puis affichait des liens vers un téléchargement qui
ne vérifiait rien. La vue prudente distribuait les adresses de la vue
négligente.

Chaque test ci-dessous échouait avant la correction, ou passait pour la
mauvaise raison. Ils décrivent la règle lue sur les intitulés du modèle :
`hr_only` exclut le salarié, `direction_only` exclut aussi les RH.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Le décor ────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company

    return Company.objects.create(name='Bâtiment Durand', slug='durand')


def _compte(django_user_model, entreprise, identifiant, role='user'):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(identifiant,
                                                        password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = role
    profil.save()
    profil.companies.add(entreprise)
    return django_user_model.objects.get(pk=utilisateur.pk)


def _salarie(entreprise, prenom, nom, utilisateur=None):
    from apps.hr.models import Employee

    return Employee.objects.create(company=entreprise, first_name=prenom,
                                   last_name=nom, user=utilisateur)


def _document(entreprise, salarie, deposant, niveau='confidential',
              visible=True, titre='Bulletin de paie janvier'):
    from apps.hr.models import EmployeePrivateDocument

    return EmployeePrivateDocument.objects.create(
        company=entreprise,
        employee=salarie,
        document_type='payslip',
        title=titre,
        file=SimpleUploadedFile(f'{titre}.pdf', b'%PDF-1.4 contenu',
                                content_type='application/pdf'),
        confidentiality_level=niveau,
        visible_to_employee=visible,
        uploaded_by=deposant,
    )


@pytest.fixture
def decor(django_user_model, entreprise):
    """Deux salariés, un RH, un patron — et le bulletin de paie de Marie."""
    rh = _compte(django_user_model, entreprise, 'rh', role='hr_manager')
    patron = _compte(django_user_model, entreprise, 'patron', role='admin')
    compte_marie = _compte(django_user_model, entreprise, 'marie')
    compte_paul = _compte(django_user_model, entreprise, 'paul')

    marie = _salarie(entreprise, 'Marie', 'Lefebvre', compte_marie)
    paul = _salarie(entreprise, 'Paul', 'Mercier', compte_paul)
    bulletin = _document(entreprise, marie, rh)

    return {
        'entreprise': entreprise, 'rh': rh, 'patron': patron,
        'marie': marie, 'compte_marie': compte_marie,
        'paul': paul, 'compte_paul': compte_paul,
        'bulletin': bulletin,
    }


def _connecte(client, utilisateur, entreprise):
    client.force_login(utilisateur)
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return client


# ── 1. La fuite elle-même ───────────────────────────────────────────────────

def test_un_collegue_ne_telecharge_pas_le_bulletin_de_paie(client, decor):
    """LE défaut. Paul n'a rien à voir avec la paie de Marie.

    Avant la correction, cette requête renvoyait le PDF — il suffisait de
    faire défiler les identifiants de documents.
    """
    _connecte(client, decor['compte_paul'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[decor['bulletin'].pk]))
    assert reponse.status_code == 404


def test_le_refus_est_inscrit_au_journal(client, decor):
    """Un journal qui n'enregistre que les succès ne dit pas qu'un compte a
    essayé deux cents identifiants avant de s'arrêter."""
    from apps.hr.models import EmployeeDocumentAccessLog

    _connecte(client, decor['compte_paul'], decor['entreprise'])
    client.get(reverse('hr:private_document_download',
                       args=[decor['bulletin'].pk]))

    trace = EmployeeDocumentAccessLog.objects.filter(
        document=decor['bulletin'], user=decor['compte_paul'])
    assert trace.count() == 1
    assert trace.first().action == 'denied'


def test_aucun_telechargement_n_est_inscrit_sur_un_refus(client, decor):
    """Le journal ne doit pas dire « téléchargé » quand rien ne l'a été."""
    from apps.hr.models import EmployeeDocumentAccessLog

    _connecte(client, decor['compte_paul'], decor['entreprise'])
    client.get(reverse('hr:private_document_download',
                       args=[decor['bulletin'].pk]))
    assert not EmployeeDocumentAccessLog.objects.filter(
        document=decor['bulletin'], action='download').exists()


# ── 2. Ceux qui ont le droit ────────────────────────────────────────────────

def test_la_salariee_telecharge_son_propre_bulletin(client, decor):
    """La correction ne doit pas fermer la porte à qui elle appartient."""
    _connecte(client, decor['compte_marie'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[decor['bulletin'].pk]))
    assert reponse.status_code == 200
    assert b'%PDF' in b''.join(reponse.streaming_content)


def test_le_telechargement_reussi_est_inscrit_au_journal(client, decor):
    from apps.hr.models import EmployeeDocumentAccessLog

    _connecte(client, decor['compte_marie'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[decor['bulletin'].pk]))
    b''.join(reponse.streaming_content)
    assert EmployeeDocumentAccessLog.objects.filter(
        document=decor['bulletin'], user=decor['compte_marie'],
        action='download').count() == 1


def test_le_responsable_rh_telecharge(client, decor):
    _connecte(client, decor['rh'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[decor['bulletin'].pk]))
    assert reponse.status_code == 200


def test_la_direction_telecharge(client, decor):
    _connecte(client, decor['patron'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[decor['bulletin'].pk]))
    assert reponse.status_code == 200


# ── 3. Les deux champs que personne ne lisait ───────────────────────────────

def test_un_document_non_visible_reste_ferme_a_la_salariee(client, decor):
    """`visible_to_employee=False` — une pièce que les RH préparent encore.

    Le champ existait depuis la première migration et la vue de
    téléchargement ne l'a jamais regardé.
    """
    doc = _document(decor['entreprise'], decor['marie'], decor['rh'],
                    visible=False, titre='Projet de licenciement')
    _connecte(client, decor['compte_marie'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[doc.pk]))
    assert reponse.status_code == 404


def test_rh_uniquement_exclut_la_salariee_meme_si_visible(client, decor):
    """Deux champs qui se contredisent : « RH uniquement » l'emporte.

    Une incohérence de saisie ne doit pas ouvrir un document marqué « RH
    uniquement » — c'est une erreur plausible, pas une hypothèse d'école.
    """
    doc = _document(decor['entreprise'], decor['marie'], decor['rh'],
                    niveau='hr_only', visible=True, titre='Note interne RH')
    _connecte(client, decor['compte_marie'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[doc.pk]))
    assert reponse.status_code == 404


def test_direction_uniquement_exclut_les_rh(client, decor):
    """« Direction uniquement » veut dire sans les RH, sinon le niveau ne
    se distinguerait pas de « RH uniquement »."""
    doc = _document(decor['entreprise'], decor['marie'], decor['patron'],
                    niveau='direction_only', titre='Dossier prud hommes')
    _connecte(client, decor['rh'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[doc.pk]))
    assert reponse.status_code == 404


def test_direction_uniquement_reste_ouvert_a_la_direction(client, decor):
    doc = _document(decor['entreprise'], decor['marie'], decor['patron'],
                    niveau='direction_only', titre='Dossier prud hommes')
    _connecte(client, decor['patron'], decor['entreprise'])
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[doc.pk]))
    assert reponse.status_code == 200


# ── 4. Les quatre autres portes ─────────────────────────────────────────────

def test_un_salarie_ne_liste_pas_les_dossiers(client, decor):
    _connecte(client, decor['compte_paul'], decor['entreprise'])
    assert client.get(
        reverse('hr:private_folder_list')).status_code == 404


def test_le_responsable_rh_liste_les_dossiers(client, decor):
    _connecte(client, decor['rh'], decor['entreprise'])
    assert client.get(
        reverse('hr:private_folder_list')).status_code == 200


def test_un_salarie_n_ouvre_pas_le_dossier_d_un_autre(client, decor):
    """Cette page montre les documents ET le journal de qui les a lus."""
    _connecte(client, decor['compte_paul'], decor['entreprise'])
    assert client.get(reverse('hr:private_folder_detail',
                              args=[decor['marie'].pk])).status_code == 404


def test_un_salarie_n_ouvre_pas_son_propre_dossier_par_cette_page(client,
                                                                  decor):
    """Volontaire : il a `mes-documents`, qui applique le filtre.

    Cette page-ci montre aussi les pièces non visibles et le journal
    d'accès ; l'ouvrir à son titulaire rendrait `visible_to_employee`
    inopérant.
    """
    _connecte(client, decor['compte_marie'], decor['entreprise'])
    assert client.get(reverse('hr:private_folder_detail',
                              args=[decor['marie'].pk])).status_code == 404


def test_un_salarie_ne_depose_rien_dans_le_dossier_d_un_autre(client, decor):
    from apps.hr.models import EmployeePrivateDocument

    _connecte(client, decor['compte_paul'], decor['entreprise'])
    reponse = client.post(
        reverse('hr:private_document_add', args=[decor['marie'].pk]),
        {'document_type': 'hr_letter', 'title': 'Faux courrier',
         'file': SimpleUploadedFile('f.pdf', b'x')})
    assert reponse.status_code == 404
    assert not EmployeePrivateDocument.objects.filter(
        title='Faux courrier').exists()


def test_un_salarie_ne_supprime_pas_un_document(client, decor):
    """Y compris le sien : effacer la sanction qui vous concerne n'est pas
    un droit que cette vue doit accorder."""
    from apps.hr.models import EmployeePrivateDocument

    _connecte(client, decor['compte_marie'], decor['entreprise'])
    reponse = client.post(reverse('hr:private_document_delete',
                                  args=[decor['bulletin'].pk]))
    assert reponse.status_code == 404
    assert EmployeePrivateDocument.objects.filter(
        pk=decor['bulletin'].pk).exists()


# ── 5. La liste du salarié, alignée sur le téléchargement ───────────────────

def test_mes_documents_cache_ce_que_le_telechargement_refuse(client, decor):
    """La liste et la porte doivent dire la même chose.

    Sans cet alignement, un document « RH uniquement » coché « visible par
    le salarié » s'affichait dans sa liste et renvoyait 404 au clic.
    """
    cache = _document(decor['entreprise'], decor['marie'], decor['rh'],
                      niveau='hr_only', visible=True, titre='Note interne RH')
    _connecte(client, decor['compte_marie'], decor['entreprise'])
    reponse = client.get(reverse('hr:my_private_documents'))
    assert reponse.status_code == 200
    affiches = {doc.pk for doc in reponse.context['documents']}
    assert decor['bulletin'].pk in affiches
    assert cache.pk not in affiches


# ── 6. Le contrôle d'entreprise, qui reste ──────────────────────────────────

def test_une_autre_societe_ne_voit_rien(client, decor, django_user_model):
    """Nécessaire et très insuffisant, mais toujours là."""
    from apps.core.models import Company

    autre = Company.objects.create(name='Toiture Martin', slug='martin')
    intrus = _compte(django_user_model, autre, 'intrus', role='admin')

    _connecte(client, intrus, autre)
    reponse = client.get(reverse('hr:private_document_download',
                                 args=[decor['bulletin'].pk]))
    assert reponse.status_code == 404


# ── 7. Les règles elles-mêmes, sans passer par HTTP ─────────────────────────

def test_un_document_sans_compte_rattache_ne_s_ouvre_a_personne(decor):
    """`employee.user` vaut None pour un intérimaire ou un salarié parti.

    Le piège est que `None == None` serait vrai : comparer les
    identifiants sans écarter None ouvrirait ces documents à tout compte
    dont le profil n'est pas rattaché.
    """
    from apps.hr.document_access import peut_voir_document

    orphelin = _salarie(decor['entreprise'], 'Jean', 'Sans-Compte')
    doc = _document(decor['entreprise'], orphelin, decor['rh'])

    assert peut_voir_document(decor['compte_paul'], doc,
                              decor['entreprise']) is False
    # Les RH, elles, y ont bien accès.
    assert peut_voir_document(decor['rh'], doc, decor['entreprise']) is True


def test_sans_entreprise_courante_rien_ne_s_ouvre(decor):
    """`request.current_company` peut être None — compte sans rattachement.

    `getattr(None, 'pk', None)` vaut None, et None == None serait vrai :
    sans l'écarter explicitement, l'absence d'entreprise ouvrirait tout.
    """
    from apps.hr.document_access import peut_voir_document

    assert peut_voir_document(decor['rh'], decor['bulletin'], None) is False


def test_un_anonyme_n_a_aucun_droit(decor):
    from django.contrib.auth.models import AnonymousUser

    from apps.hr.document_access import (
        peut_gerer_les_dossiers, peut_voir_document,
    )

    anonyme = AnonymousUser()
    assert peut_voir_document(anonyme, decor['bulletin'],
                              decor['entreprise']) is False
    assert peut_gerer_les_dossiers(anonyme) is False


def test_le_role_responsable_n_a_pas_acces(client, decor, django_user_model):
    """Choix signalé, et réversible : « manager » n'a pas accès.

    Donner à tout chef d'équipe la lecture des bulletins de paie et des
    sanctions de ses subordonnés est une décision d'entreprise, et rien
    dans le modèle ne relie un responsable à une équipe. Pour l'ouvrir :
    ajouter 'manager' à ROLES_RH dans apps/hr/document_access.py.
    """
    chef = _compte(django_user_model, decor['entreprise'], 'chef',
                   role='manager')
    _connecte(client, chef, decor['entreprise'])
    assert client.get(reverse('hr:private_document_download',
                              args=[decor['bulletin'].pk])).status_code == 404


# ── 8. L'autre porte : les widgets du tableau de bord ───────────────────────

def test_un_widget_ne_nomme_pas_les_documents_d_autrui(decor):
    """La même fuite, par le tableau de bord.

    `get_hr_expiring_documents_data` nomme le salarié ET le document
    (« Visite médicale — Marie Lefebvre ») et n'était borné que par
    l'entreprise. Fermer la vue de téléchargement sans fermer celle-ci
    n'aurait déplacé la fuite que d'une porte.
    """
    from datetime import date, timedelta

    from apps.dashboard.widgets import get_hr_expiring_documents_data

    decor['bulletin'].expires_at = date.today() + timedelta(days=10)
    decor['bulletin'].save(update_fields=['expires_at'])

    vu_par_paul = get_hr_expiring_documents_data(decor['compte_paul'],
                                                 decor['entreprise'])
    assert vu_par_paul['documents'] == []
    assert vu_par_paul['total'] == 0

    vu_par_rh = get_hr_expiring_documents_data(decor['rh'],
                                               decor['entreprise'])
    assert [doc.pk for doc in vu_par_rh['documents']] == [
        decor['bulletin'].pk]


def test_le_widget_a_soixante_jours_est_borne_aussi(decor):
    from datetime import date, timedelta

    from apps.dashboard.widgets import get_documents_expiring_soon_data

    decor['bulletin'].expires_at = date.today() + timedelta(days=45)
    decor['bulletin'].save(update_fields=['expires_at'])

    assert get_documents_expiring_soon_data(
        decor['compte_paul'], decor['entreprise'])['documents'] == []
    assert get_documents_expiring_soon_data(
        decor['rh'], decor['entreprise'])['count'] == 1


def test_le_widget_rh_ne_montre_pas_les_pieces_direction(decor):
    """« Direction uniquement » tient aussi dans les listes."""
    from datetime import date, timedelta

    from apps.dashboard.widgets import get_hr_expiring_documents_data

    reserve = _document(decor['entreprise'], decor['marie'], decor['patron'],
                        niveau='direction_only', titre='Dossier prud hommes')
    reserve.expires_at = date.today() + timedelta(days=5)
    reserve.save(update_fields=['expires_at'])

    vu_par_rh = get_hr_expiring_documents_data(decor['rh'],
                                               decor['entreprise'])
    assert reserve.pk not in {doc.pk for doc in vu_par_rh['documents']}

    vu_par_patron = get_hr_expiring_documents_data(decor['patron'],
                                                   decor['entreprise'])
    assert reserve.pk in {doc.pk for doc in vu_par_patron['documents']}


def test_mon_widget_cache_ce_que_le_telechargement_refuse(decor):
    """Le widget du salarié, aligné sur sa liste et sur la porte."""
    from apps.dashboard.widgets import get_hr_my_private_documents_data

    cache = _document(decor['entreprise'], decor['marie'], decor['rh'],
                      niveau='hr_only', visible=True, titre='Note interne RH')

    affiches = {doc.pk for doc in get_hr_my_private_documents_data(
        decor['compte_marie'], decor['entreprise'])['documents']}
    assert decor['bulletin'].pk in affiches
    assert cache.pk not in affiches


# -- La decision sur le role « manager », verrouillee -----------------------


def test_le_role_manager_n_accede_pas_aux_dossiers_prives():
    """DECISION du proprietaire du projet, confirmee le 27 octobre 2026.

    Le role « Responsable » (manager) ne voit pas les contrats, bulletins
    de paie ni sanctions. La raison est dans l'en-tete de
    apps/hr/document_access.py, et elle tient surtout a ceci : rien dans le
    modele ne relie un responsable a une equipe. Ouvrir ce role donnerait
    donc acces aux dossiers de TOUS les salaries de l'entreprise, et pas
    seulement des siens -- un elargissement bien plus large qu'il n'y
    parait.

    Ce test n'empeche pas de changer d'avis : il empeche de le faire par
    accident, au detour d'une refonte des roles.
    """
    from apps.hr.document_access import ROLES_DIRECTION, ROLES_RH

    assert 'manager' not in ROLES_RH
    assert 'manager' not in ROLES_DIRECTION
    assert ROLES_RH == ('hr_manager',)


def test_la_direction_ne_designe_que_deux_roles():
    """Il n'existe pas de role « direction » dans ROLE_CHOICES.

    ROLES_DIRECTION en est l'equivalent le plus proche ; si un vrai role
    apparait un jour, ce test rappellera de le traiter ici.
    """
    from apps.accounts.models import ROLE_CHOICES
    from apps.hr.document_access import ROLES_DIRECTION

    existants = {code for code, _libelle in ROLE_CHOICES}
    assert set(ROLES_DIRECTION) <= existants, (
        'ROLES_DIRECTION cite un role qui n existe pas dans ROLE_CHOICES.')
    assert 'direction' not in existants
