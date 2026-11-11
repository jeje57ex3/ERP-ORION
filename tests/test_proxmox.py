"""Interroger l'hyperviseur : ce que la VM ne peut pas voir d'elle-même.

CE QUE CELA RÉPARE

L'écran des disques voyait ce que le système d'exploitation voit, et rien de
ce que l'hyperviseur sait. Deux situations se confondaient donc sous le même
« aucun disque détecté » :

  * aucun disque n'a été ajouté à la VM — l'action est sur l'hyperviseur ;
  * un disque EST ajouté, mais l'ajout à chaud n'a pas été transmis au
    noyau — un redémarrage suffit, et c'est une action tout autre.

LA PROPRIÉTÉ DE SÛRETÉ

Le client n'expose que des GET, et `_appeler` refuse tout autre verbe. Le
jeton stocké dans l'ERP ne peut donc rien écrire sur l'hyperviseur depuis
ici, quels que soient ses droits côté Proxmox. Un jeton d'hyperviseur logé
dans la machine virtuelle qu'il gouverne renverse la confiance ; tant que le
client ne sait que lire, le pire d'une compromission de l'ERP est la
divulgation d'un inventaire.
"""
import pytest
import requests
from cryptography.fernet import Fernet
from django.test import override_settings


CLE = Fernet.generate_key().decode()

CONFIG_VM = {
    'name': 'orion-erp',
    'scsi0': 'local-lvm:vm-100-disk-0,size=32G',
    'scsi1': 'local-lvm:vm-100-disk-1,size=500G',
    'ide2': 'local:iso/debian.iso,media=cdrom',
    'efidisk0': 'local-lvm:vm-100-disk-2,size=4M',
    'unused0': 'local-lvm:vm-100-disk-9',
    'memory': '8192',
}

STOCKAGES = [
    {'storage': 'local-lvm', 'type': 'lvmthin', 'content': 'images,rootdir',
     'total': 900 * 1024 ** 3, 'avail': 400 * 1024 ** 3, 'enabled': 1},
    {'storage': 'sauvegardes', 'type': 'dir', 'content': 'backup',
     'total': 2000 * 1024 ** 3, 'avail': 1500 * 1024 ** 3, 'enabled': 1},
    {'storage': 'hors-service', 'type': 'dir', 'content': 'images',
     'total': 10 * 1024 ** 3, 'avail': 5 * 1024 ** 3, 'enabled': 0},
]


class ReponseSimulee:
    def __init__(self, charge, status_code=200, json_valide=True):
        self._charge = charge
        self.status_code = status_code
        self._json_valide = json_valide

    def json(self):
        if not self._json_valide:
            raise ValueError('pas du JSON')
        return {'data': self._charge}


@pytest.fixture
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def reglages(db):
    """Des réglages complets. Le secret est chiffré pour de bon."""
    from apps.system_health.models import ReglagesProxmox

    with override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE):
        obj = ReglagesProxmox.get_global()
        obj.actif = True
        obj.hote = '192.168.1.10'
        obj.noeud = 'pve'
        obj.vmid = 100
        obj.jeton_id = 'orion@pam!erp'
        obj.jeton_secret = 'secret-de-test'
        obj.save()
    return obj


def _repondeur(par_chemin, enregistre=None):
    """Un faux `requests.get` qui répond selon le chemin appelé."""
    def _get(url, headers=None, verify=None, timeout=None):
        if enregistre is not None:
            enregistre.append({'url': url, 'headers': headers or {},
                               'verify': verify, 'timeout': timeout})
        for fragment, reponse in par_chemin.items():
            if fragment in url:
                if isinstance(reponse, Exception):
                    raise reponse
                return reponse
        return ReponseSimulee(None, status_code=404)
    return _get


# ── 1. La propriété de sûreté : lecture seule ────────────────────────────────

@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_client_refuse_toute_methode_autre_que_get(reglages):
    """LA GARANTIE CENTRALE.

    Il n'y a pas d'écriture à désactiver : il n'en existe aucune. Ce garde-fou
    est là pour qu'un ajout futur tombe dessus et doive justifier le
    changement de compromis.
    """
    from apps.system_health import proxmox

    client = proxmox.ClientProxmox(reglages)
    for methode in ('POST', 'PUT', 'DELETE', 'PATCH'):
        with pytest.raises(proxmox.ProxmoxRefuse) as refus:
            client._appeler('/nodes/pve/qemu/100/config', methode=methode)
        assert 'lecture seule' in str(refus.value)


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_aucune_methode_d_ecriture_n_existe_sur_le_client():
    """Si quelqu'un ajoute « creer_un_disque », ce test doit tomber et le
    faire discuter — pas passer en silence."""
    from apps.system_health import proxmox

    interdits = [nom for nom in dir(proxmox.ClientProxmox)
                 if any(verbe in nom.lower() for verbe in
                        ('creer', 'create', 'ajouter', 'add', 'supprimer',
                         'delete', 'set_', 'modifier', 'ecrire', 'post'))]
    assert interdits == [], f'méthodes d’écriture apparues : {interdits}'


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_secret_voyage_dans_un_entete_jamais_dans_l_adresse(
        reglages, monkeypatch):
    """Une adresse se retrouve dans les journaux d'accès, les traces et les
    messages d'erreur. Un en-tête, non."""
    from apps.system_health import proxmox

    appels = []
    monkeypatch.setattr(
        requests, 'get',
        _repondeur({'/version': ReponseSimulee({'version': '8.2'})}, appels))

    proxmox.ClientProxmox(reglages).version()

    assert len(appels) == 1
    assert 'secret-de-test' not in appels[0]['url']
    assert appels[0]['headers']['Authorization'] == (
        'PVEAPIToken=orion@pam!erp=secret-de-test')


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_secret_est_retire_des_messages_d_erreur(reglages, monkeypatch):
    """Par précaution : une bibliothèque tierce peut très bien recopier un
    en-tête dans son exception."""
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/version': requests.exceptions.ConnectionError(
            'echec avec secret-de-test dans le texte'),
    }))

    with pytest.raises(proxmox.ProxmoxIndisponible) as erreur:
        proxmox.ClientProxmox(reglages).version()

    assert 'secret-de-test' not in str(erreur.value)
    assert 'secret retiré' in str(erreur.value)


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_secret_est_chiffre_en_base(reglages):
    assert reglages.jeton_secret_chiffre
    assert 'secret-de-test' not in reglages.jeton_secret_chiffre
    assert reglages.jeton_secret == 'secret-de-test'
    assert reglages.secret_illisible is False


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_un_secret_illisible_se_distingue_d_un_secret_absent(reglages):
    """Même distinction que pour le mot de passe SMTP : les confondre envoie
    chercher une faute de frappe là où la base a été restaurée sur une autre
    clé."""
    with override_settings(
            ORION_SECRET_ENCRYPTION_KEY=Fernet.generate_key().decode()):
        assert reglages.jeton_secret == ''
        assert reglages.secret_enregistre is True
        assert reglages.secret_illisible is True


# ── 2. La lecture de la configuration ────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_les_disques_sont_extraits_de_la_configuration(reglages, monkeypatch):
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': ReponseSimulee(CONFIG_VM)}))

    disques = proxmox.ClientProxmox(reglages).disques_declares()
    cles = [d['cle'] for d in disques]

    assert 'scsi0' in cles and 'scsi1' in cles
    # Un support optique n'est pas un disque.
    assert 'ide2' not in cles
    # Le disque EFI est rendu, mais marqué système : le compter comme un
    # disque de données tromperait sur ce qui est disponible.
    assert 'efidisk0' in cles
    assert next(d for d in disques if d['cle'] == 'efidisk0')['systeme'] is True
    # Un volume détaché occupe de la place : il doit se voir, marqué.
    assert next(d for d in disques if d['cle'] == 'unused0')['detache'] is True


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_les_tailles_sont_converties_en_octets(reglages, monkeypatch):
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': ReponseSimulee(CONFIG_VM)}))

    disques = {d['cle']: d['taille_octets']
               for d in proxmox.ClientProxmox(reglages).disques_declares()}

    assert disques['scsi0'] == 32 * 1024 ** 3
    assert disques['scsi1'] == 500 * 1024 ** 3
    assert disques['efidisk0'] == 4 * 1024 ** 2


@pytest.mark.django_db
def test_une_taille_absente_rend_none_et_non_zero():
    """« Inconnue » et « vide » ne sont pas la même chose : afficher 0 pour
    un disque dont on ignore la taille serait un mensonge."""
    from apps.system_health.proxmox import _taille_en_octets

    assert _taille_en_octets('local-lvm:vm-100-disk-9') is None
    assert _taille_en_octets('local:disk,size=512') == 512
    assert _taille_en_octets('local:disk,size=1T') == 1024 ** 4


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_seuls_les_pools_qui_acceptent_des_images_sont_proposes(
        reglages, monkeypatch):
    """Proposer un pool de sauvegardes pour y créer un disque mènerait à une
    erreur que l'exploitant ne pourrait pas interpréter."""
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/storage': ReponseSimulee(STOCKAGES)}))

    pools = proxmox.ClientProxmox(reglages).stockages_utilisables()
    noms = [p['nom'] for p in pools]

    assert 'local-lvm' in noms
    assert 'sauvegardes' not in noms, 'un pool de backup a été proposé'
    assert 'hors-service' not in noms, 'un pool désactivé a été proposé'


# ── 3. Les refus, et leurs messages ──────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_un_jeton_refuse_le_dit_clairement(reglages, monkeypatch):
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': ReponseSimulee(None, status_code=401)}))

    with pytest.raises(proxmox.ProxmoxRefuse) as refus:
        proxmox.ClientProxmox(reglages).config_de_la_machine()

    motif = str(refus.value)
    assert 'jeton' in motif
    assert 'orion@pam!erp' in motif
    assert 'secret-de-test' not in motif


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_un_certificat_auto_signe_explique_quoi_faire(reglages, monkeypatch):
    """Proxmox s'installe avec un certificat auto-signé : c'est le premier
    échec qu'un exploitant rencontre, il doit être actionnable."""
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/version': requests.exceptions.SSLError('certificat auto-signé')}))

    with pytest.raises(proxmox.ProxmoxIndisponible) as erreur:
        proxmox.ClientProxmox(reglages).version()

    assert 'auto-signé' in str(erreur.value)
    assert 'Vérifier le certificat' in str(erreur.value)


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_une_reponse_qui_n_est_pas_du_json_est_signalee(reglages, monkeypatch):
    """L'adresse pointe peut-être ailleurs que sur l'API Proxmox."""
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/version': ReponseSimulee(None, json_valide=False)}))

    with pytest.raises(proxmox.ProxmoxIndisponible) as erreur:
        proxmox.ClientProxmox(reglages).version()
    assert 'JSON' in str(erreur.value)


@pytest.mark.django_db
def test_des_reglages_incomplets_sont_refuses_avant_tout_appel(db,
                                                               monkeypatch):
    """Aucun appel réseau ne doit partir avec des réglages vides."""
    from apps.system_health import proxmox
    from apps.system_health.models import ReglagesProxmox

    appels = []
    monkeypatch.setattr(requests, 'get', _repondeur({}, appels))

    reglages = ReglagesProxmox.get_global()
    with pytest.raises(proxmox.ProxmoxIndisponible):
        proxmox.ClientProxmox(reglages).version()
    assert appels == [], 'un appel est parti malgré des réglages incomplets'


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_reglage_de_certificat_est_bien_transmis(reglages, monkeypatch):
    from apps.system_health import proxmox

    appels = []
    monkeypatch.setattr(requests, 'get', _repondeur(
        {'/version': ReponseSimulee({'version': '8.2'})}, appels))

    proxmox.ClientProxmox(reglages).version()
    assert appels[0]['verify'] is True

    reglages.verifier_le_certificat = False
    reglages.save()
    proxmox.ClientProxmox(reglages).version()
    assert appels[1]['verify'] is False


# ── 4. Le test de connexion, et la correction du type ────────────────────────

@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_test_corrige_le_type_de_machine_quand_l_autre_repond(
        reglages, monkeypatch):
    """Un conteneur et une VM n'ont pas la même adresse d'API, et se tromper
    rend un 404 qui ressemble à « nœud inconnu ».

    Quand l'autre type répond, on le dit ET on corrige le réglage : on vient
    d'en avoir la preuve, le laisser faux ferait échouer les appels suivants.
    """
    from apps.system_health import proxmox

    def _get(url, headers=None, verify=None, timeout=None):
        if '/version' in url:
            return ReponseSimulee({'version': '8.2'})
        if '/qemu/' in url:
            return ReponseSimulee(None, status_code=404)
        if '/lxc/' in url:
            return ReponseSimulee({'hostname': 'orion-ct', 'rootfs': 'x:y,size=20G'})
        return ReponseSimulee(None, status_code=404)

    monkeypatch.setattr(requests, 'get', _get)

    reussi, motif = proxmox.tester(reglages)
    assert reussi is True, motif
    assert 'lxc' in motif

    reglages.refresh_from_db()
    assert reglages.type_de_machine == 'lxc'


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_le_test_reussi_est_consigne(reglages, monkeypatch):
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/version': ReponseSimulee({'version': '8.2'}),
        '/config': ReponseSimulee(CONFIG_VM),
    }))

    reussi, motif = proxmox.tester(reglages)
    assert reussi is True
    assert 'orion-erp' in motif

    reglages.refresh_from_db()
    assert reglages.dernier_appel_reussi is True
    assert reglages.dernier_appel_le is not None


@pytest.mark.django_db
def test_le_test_sans_adresse_le_dit_sans_appeler(db):
    from apps.system_health import proxmox
    from apps.system_health.models import ReglagesProxmox

    reussi, motif = proxmox.tester(ReglagesProxmox.get_global())
    assert reussi is False
    assert 'adresse' in motif.lower()


# ── 5. LA COMPARAISON : le diagnostic qui manquait ───────────────────────────

@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_un_disque_declare_mais_invisible_est_diagnostique(reglages,
                                                           monkeypatch):
    """LE CAS QUI MOTIVAIT TOUT CE LOT.

    « le disque n'est toujours pas ajouté sur la vm » peut vouloir dire deux
    choses opposées, et l'écran les confondait sous « aucun disque détecté ».
    Ici Proxmox en déclare deux et le système n'en voit qu'un : le disque EST
    ajouté, c'est le noyau qui ne l'a pas vu. L'action est un redémarrage, et
    non un passage sur l'hyperviseur.
    """
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': ReponseSimulee(CONFIG_VM),
        '/storage': ReponseSimulee(STOCKAGES),
    }))

    inventaire = proxmox.inventaire(reglages, use_cache=False)
    assert inventaire['joignable'] is True

    # Le système ne voit qu'un disque, l'hyperviseur en déclare deux
    # (scsi0 et scsi1 ; efidisk0 est système, unused0 est détaché).
    comparaison = proxmox.comparer_avec_le_systeme(
        inventaire, [{'peripherique': '/dev/sda'}])

    assert comparaison['comparable'] is True
    assert comparaison['coherent'] is False
    assert comparaison['nombre_declare'] == 2
    assert comparaison['nombre_vu'] == 1
    assert 'redémarrage' in comparaison['diagnostic']


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_quand_tout_concorde_le_diagnostic_le_dit(reglages, monkeypatch):
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': ReponseSimulee(CONFIG_VM),
        '/storage': ReponseSimulee(STOCKAGES),
    }))

    inventaire = proxmox.inventaire(reglages, use_cache=False)
    comparaison = proxmox.comparer_avec_le_systeme(
        inventaire, [{'peripherique': '/dev/sda'},
                     {'peripherique': '/dev/sdb'}])

    assert comparaison['coherent'] is True
    assert 'concordent' in comparaison['diagnostic']


@pytest.mark.django_db
def test_sans_inventaire_du_systeme_on_ne_conclut_pas():
    """« Je ne sais pas ce que le système voit » ne doit pas se lire « zéro
    disque » — ce serait inventer une incohérence."""
    from apps.system_health import proxmox

    comparaison = proxmox.comparer_avec_le_systeme(
        {'joignable': True, 'disques': [
            {'cle': 'scsi0', 'systeme': False, 'detache': False}]},
        None)

    assert comparaison['comparable'] is False
    assert 'inventorié' in comparaison['motif']


@pytest.mark.django_db
def test_sans_hyperviseur_interroge_aucune_comparaison():
    from apps.system_health import proxmox

    comparaison = proxmox.comparer_avec_le_systeme(
        {'joignable': False}, [{'peripherique': '/dev/sda'}])
    assert comparaison['comparable'] is False


# ── 6. L'inventaire ne lève jamais, et se met en cache ───────────────────────

@pytest.mark.django_db
def test_l_inventaire_sans_reglages_rend_un_dict_vide(db):
    """L'écran des disques doit rester consultable sans cette fonction."""
    from apps.system_health import proxmox

    resultat = proxmox.inventaire(use_cache=False)
    assert resultat['configure'] is False
    assert resultat['joignable'] is False
    assert resultat['disques'] == []


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_l_inventaire_ne_leve_jamais_quand_l_hote_est_muet(reglages,
                                                           monkeypatch):
    from apps.system_health import proxmox

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': requests.exceptions.ConnectionError('injoignable')}))

    resultat = proxmox.inventaire(reglages, use_cache=False)
    assert resultat['joignable'] is False
    assert 'ne répond pas' in resultat['erreur']


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_l_inventaire_est_mis_en_cache(reglages, monkeypatch):
    """Sans cache, la page des disques appellerait l'hôte à chaque
    affichage — et attendrait dix secondes quand il ne répond pas."""
    from apps.system_health import proxmox

    appels = []
    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': ReponseSimulee(CONFIG_VM),
        '/storage': ReponseSimulee(STOCKAGES),
    }, appels))

    proxmox.oublier_l_inventaire()
    proxmox.inventaire(reglages)
    nombre = len(appels)
    proxmox.inventaire(reglages)
    assert len(appels) == nombre, 'le second appel n’a pas servi le cache'

    proxmox.oublier_l_inventaire()
    proxmox.inventaire(reglages)
    assert len(appels) > nombre, 'le cache n’a pas été vidé'


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_un_echec_est_aussi_mis_en_cache(reglages, monkeypatch):
    """Sinon un hôte injoignable ferait attendre à chaque rafraîchissement."""
    from apps.system_health import proxmox

    appels = []
    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': requests.exceptions.ConnectionError('injoignable'),
    }, appels))

    proxmox.oublier_l_inventaire()
    proxmox.inventaire(reglages)
    nombre = len(appels)
    proxmox.inventaire(reglages)
    assert len(appels) == nombre


# ── 7. Le contrôle mensuel ───────────────────────────────────────────────────

@pytest.mark.django_db
def test_hyperviseur_non_configure_n_est_pas_un_reproche(db):
    """C'est une fonction facultative : la signaler en avertissement
    remplirait le rapport d'un reproche permanent."""
    from apps.system_health.controle_installation import OK, _hyperviseur

    etat, message, _ = _hyperviseur()
    assert etat == OK
    assert 'facultatif' in message


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_hyperviseur_configure_mais_muet_est_signale(reglages, monkeypatch):
    from apps.system_health.controle_installation import (AVERTISSEMENT,
                                                          _hyperviseur)

    monkeypatch.setattr(requests, 'get', _repondeur({
        '/config': requests.exceptions.ConnectionError('injoignable')}))

    etat, message, _ = _hyperviseur()
    assert etat == AVERTISSEMENT
    assert 'ne répond pas' in message


# ── 8. La page ───────────────────────────────────────────────────────────────

def _super_admin(client, django_user_model):
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')
    client.force_login(utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_la_page_s_affiche_et_rappelle_la_lecture_seule(client,
                                                        django_user_model):
    _super_admin(client, django_user_model)

    reponse = client.get('/orion-admin/sante-systeme/proxmox/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Lecture seule' in contenu
    assert 'PVEAuditor' in contenu
    # La page doit dire ce qu'elle ne fait PAS : ajouter un disque.
    assert 'n’ajoute pas de disque' in contenu or 'ajoute pas de disque' in contenu


@pytest.mark.django_db
def test_la_page_est_refusee_a_un_salarie(client, django_user_model):
    """Un jeton d'hyperviseur se règle ici : la page n'est pas publique."""
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    salarie = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    client.force_login(salarie)

    reponse = client.get('/orion-admin/sante-systeme/proxmox/')
    assert reponse.status_code == 403


@pytest.mark.django_db
@override_settings(ORION_SECRET_ENCRYPTION_KEY=CLE)
def test_enregistrer_la_page_ne_detruit_pas_le_secret(client,
                                                      django_user_model):
    """Même piège que pour le mot de passe SMTP : un champ vide conserve."""
    from apps.system_health.models import ReglagesProxmox

    _super_admin(client, django_user_model)
    reglages = ReglagesProxmox.get_global()
    reglages.jeton_secret = 'secret-de-test'
    reglages.hote = '192.168.1.10'
    reglages.save()

    client.post('/orion-admin/sante-systeme/proxmox/', {
        'action': 'enregistrer',
        'hote': '192.168.1.10',
        'port': '8006',
        'noeud': 'pve',
        'vmid': '100',
        'type_de_machine': 'qemu',
        'jeton_id': 'orion@pam!erp',
        'jeton_secret': '',
        'delai_secondes': '10',
        'verifier_le_certificat': 'on',
    })

    relu = ReglagesProxmox.get_global()
    assert relu.noeud == 'pve'
    assert relu.jeton_secret == 'secret-de-test', 'le secret a été effacé'


@pytest.mark.django_db
def test_un_identifiant_de_jeton_sans_point_d_exclamation_est_signale(
        client, django_user_model):
    """Proxmox attend « utilisateur@pam!nom ». Un identifiant d'utilisateur
    seul donne un 401 qui n'explique rien."""
    _super_admin(client, django_user_model)

    reponse = client.post('/orion-admin/sante-systeme/proxmox/', {
        'action': 'enregistrer',
        'hote': '192.168.1.10',
        'port': '8006',
        'noeud': 'pve',
        'vmid': '100',
        'type_de_machine': 'qemu',
        'jeton_id': 'orion@pam',
        'delai_secondes': '10',
    }, follow=True)

    textes = [str(m) for m in reponse.context['messages']]
    assert any('!' in t and 'jeton' in t.lower() for t in textes), textes


@pytest.mark.django_db
def test_decocher_la_verification_du_certificat_avertit(client,
                                                        django_user_model):
    """Ce n'est pas interdit — c'est parfois nécessaire — mais ça ne doit pas
    passer en silence."""
    _super_admin(client, django_user_model)

    reponse = client.post('/orion-admin/sante-systeme/proxmox/', {
        'action': 'enregistrer',
        'hote': '192.168.1.10',
        'port': '8006',
        'noeud': 'pve',
        'vmid': '100',
        'type_de_machine': 'qemu',
        'delai_secondes': '10',
    }, follow=True)

    textes = [str(m) for m in reponse.context['messages']]
    assert any('certificat' in t.lower() for t in textes), textes


@pytest.mark.django_db
def test_un_port_illisible_conserve_la_valeur_en_place(client,
                                                       django_user_model):
    from apps.system_health.models import ReglagesProxmox

    _super_admin(client, django_user_model)
    reglages = ReglagesProxmox.get_global()
    reglages.port = 8006
    reglages.save()

    client.post('/orion-admin/sante-systeme/proxmox/', {
        'action': 'enregistrer',
        'hote': '192.168.1.10',
        'port': 'huit-mille-six',
        'noeud': 'pve',
        'vmid': '100',
        'type_de_machine': 'qemu',
        'delai_secondes': '10',
    })

    assert ReglagesProxmox.get_global().port == 8006
