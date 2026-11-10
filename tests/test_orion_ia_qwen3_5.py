# -*- coding: utf-8 -*-
"""Le passage de qwen2.5 à qwen3.5, et les deux pièges qu'il ouvre.

PREMIER PIÈGE : LE NOM NE SE DÉDUIT PAS DE L'ANCIEN.

qwen2.5 nommait ses modèles « qwen2.5:3b-instruct ». qwen3.5 a abandonné le
suffixe « -instruct » et n'a pas de taille « 3b » — ses tailles sont 0.8b, 2b,
4b, 9b. Remplacer « 2.5 » par « 3.5 » produit donc un nom qui n'existe pas, et
Ollama répond 404 sur CHAQUE question pour un nom inconnu. Le défaut ne se voit
ni à la relecture du diff ni au démarrage : seulement à la première question.

SECOND PIÈGE : QWEN3.5 RÉFLÉCHIT AVANT DE RÉPONDRE.

Deux conséquences mesurables, et une troisième de notre propre fait :

  1. les jetons de réflexion sont pris SUR LE PLAFOND de génération. À 600
     jetons — le réglage par défaut — un modèle qui réfléchit peut les
     dépenser entièrement et renvoyer une réponse VIDE ;
  2. la réflexion n'arrive pas dans `content`. En flux, l'utilisateur voit
     donc un silence complet pendant toute sa durée, alors que le flux avait
     été ajouté précisément pour supprimer ce silence ;
  3. et la correction évidente — envoyer `think: false` partout, par
     précaution — casserait toute installation restée sur qwen2.5 : Ollama
     REFUSE la requête entière, HTTP 400 « does not support thinking », quand
     l'option est adressée à un modèle qui ne la connaît pas.

D'où une capacité DEMANDÉE au démon plutôt que déduite du nom. Ces tests
tiennent les deux sens de l'erreur, parce qu'ils ne se compensent pas : l'un
rend l'assistant lent, l'autre le rend muet.
"""

import os
import re
import shutil
import subprocess

import pytest

from apps.orion_ai import providers as mod
from apps.orion_ai.providers import LocalAIProvider

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_IA = os.path.join(
    RACINE, 'deployment', 'proxmox-appliance', 'scripts', 'orion-ai.sh')
SCRIPT_VERIF = os.path.join(
    RACINE, 'deployment', 'proxmox-appliance', 'scripts', 'orion-verifier.sh')

MODELE = 'qwen3.5:4b-q4_K_M'

REPONSE_CHAT = {
    'message': {'content': 'Bonjour.'},
    'prompt_eval_count': 10,
    'eval_count': 5,
    'eval_duration': 1_000_000_000,
}


def _lire(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


class _Reponse:
    def __init__(self, donnees, status_code=200):
        self._donnees = donnees
        self.status_code = status_code
        self.text = ''

    def json(self):
        if isinstance(self._donnees, Exception):
            raise self._donnees
        return self._donnees

    # Le flux d'Ollama : une ligne de JSON par jeton.
    def iter_lines(self, decode_unicode=False):
        import json
        yield json.dumps({'message': {'content': 'Bonjour.'}})
        yield json.dumps(dict(REPONSE_CHAT, done=True))


@pytest.fixture(autouse=True)
def _cache_vide():
    """Le cache des capacités ne doit pas passer d'un test à l'autre.

    Il est volontairement global au processus — une capacité par modèle, pas
    par requête. Sans ce nettoyage, l'ordre des tests déciderait du résultat.
    """
    mod.oublier_les_capacites()
    yield
    mod.oublier_les_capacites()


def _brancher(monkeypatch, capacites=None, show_status=200, show_json=None):
    """Branche /api/show et /api/chat, et retourne les charges envoyées."""
    envois = []

    def faux_post(url, **kwargs):
        envois.append({'url': url, 'json': kwargs.get('json')})
        if url.endswith('/api/show'):
            if show_json is not None:
                return _Reponse(show_json, show_status)
            return _Reponse({'capabilities': list(capacites or ())},
                            show_status)
        return _Reponse(REPONSE_CHAT)

    monkeypatch.setattr('apps.orion_ai.providers.http_requests.post',
                        faux_post)
    return envois


def _charge_du_chat(envois):
    for envoi in envois:
        if envoi['url'].endswith('/api/chat'):
            return envoi['json']
    raise AssertionError('aucune requete /api/chat : %r' % envois)


# ─── Le sens qui rend MUET : ne pas envoyer `think` à qui l'ignore ───────────

def test_aucun_think_sur_un_modele_qui_ne_sait_pas_reflechir(monkeypatch):
    """Le cas de toute installation restée sur qwen2.5.

    Ollama refuse la requête ENTIÈRE avec un 400 — pas la seule option. Un
    envoi inconditionnel n'aurait donc pas dégradé l'assistant, il l'aurait
    arrêté, et le message rendu aurait été « le moteur local a refusé la
    requête (HTTP 400) », qui ne désigne pas la cause.
    """
    envois = _brancher(monkeypatch, capacites=('completion', 'tools'))

    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}],
        model='qwen2.5:3b-instruct',
    )

    assert 'think' not in _charge_du_chat(envois)


def test_une_capacite_inconnue_n_envoie_rien(monkeypatch):
    """Le démon injoignable ne vaut pas « ce modèle ne réfléchit pas ».

    Les deux erreurs n'ont pas le même prix : omettre `think` laisse un modèle
    à raisonnement répondre lentement — gênant, réparable ; l'envoyer à un
    modèle qui l'ignore rend l'assistant muet. L'incertitude penche donc du
    côté réparable, et c'est ce choix que ce test garde.
    """
    envois = _brancher(monkeypatch, show_status=500)

    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}], model=MODELE,
    )

    assert 'think' not in _charge_du_chat(envois)


def test_une_reponse_illisible_n_interrompt_pas_la_question(monkeypatch):
    """Un /api/show qui ne rend pas du JSON ne doit pas faire échouer le chat."""
    envois = _brancher(monkeypatch, show_json=ValueError('pas du json'))

    resultat = LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}], model=MODELE,
    )

    assert resultat['content'] == 'Bonjour.'
    assert 'think' not in _charge_du_chat(envois)


# ─── Le sens qui rend LENT, ou VIDE : couper la réflexion quand elle existe ──

def test_la_reflexion_est_coupee_sur_un_modele_qui_la_connait(monkeypatch):
    """Sans cela, les 600 jetons du plafond partent en réflexion."""
    envois = _brancher(
        monkeypatch, capacites=('completion', 'tools', 'thinking'))

    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}],
        model=MODELE, max_output_tokens=600,
    )

    charge = _charge_du_chat(envois)
    assert charge['think'] is False
    assert charge['options']['num_predict'] == 600


def test_l_exploitant_peut_la_rallumer(monkeypatch):
    """Le réglage existe : une machine confortable peut en profiter."""
    envois = _brancher(
        monkeypatch, capacites=('completion', 'thinking'))

    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}],
        model=MODELE, thinking=True,
    )

    assert _charge_du_chat(envois)['think'] is True


def test_le_flux_coupe_aussi_la_reflexion(monkeypatch):
    """C'est en flux que la réflexion coûte le plus cher.

    Elle n'arrive pas dans `content` : rien ne s'affiche pendant toute sa
    durée. Le silence que le flux devait supprimer reviendrait, aggravé.
    """
    envois = []

    def faux_post(url, **kwargs):
        envois.append({'url': url, 'json': kwargs.get('json')})
        if url.endswith('/api/show'):
            return _Reponse({'capabilities': ['completion', 'thinking']})
        return _Reponse(REPONSE_CHAT)

    monkeypatch.setattr('apps.orion_ai.providers.http_requests.post',
                        faux_post)

    list(LocalAIProvider().generate_stream(
        messages=[{'role': 'user', 'content': 'bonjour'}], model=MODELE,
    ))

    assert _charge_du_chat(envois)['think'] is False


# ─── Le cache : une capacité par modèle, et jamais un échec ──────────────────

def test_la_capacite_n_est_demandee_qu_une_fois(monkeypatch):
    """Une question ne doit pas coûter deux allers-retours au démon."""
    envois = _brancher(monkeypatch, capacites=('thinking',))

    for _ in range(3):
        LocalAIProvider().generate(
            messages=[{'role': 'user', 'content': 'bonjour'}], model=MODELE,
        )

    shows = [e for e in envois if e['url'].endswith('/api/show')]
    assert len(shows) == 1, shows


def test_un_echec_n_est_pas_mis_en_cache(monkeypatch):
    """Sinon un démon indisponible à la première question figerait
    « ce modèle ne réfléchit pas » pour toute la durée du processus — et la
    réflexion resterait active jusqu'au prochain redémarrage."""
    _brancher(monkeypatch, show_status=503)
    assert mod.capacites_du_modele('http://x', MODELE) == ()

    envois = _brancher(monkeypatch, capacites=('thinking',))
    assert mod.capacites_du_modele('http://x', MODELE) == ('thinking',)
    assert [e for e in envois if e['url'].endswith('/api/show')]


# ─── Les modèles présents, et « je n'ai pas pu savoir » ──────────────────────

def test_une_liste_vide_ne_veut_pas_dire_aucun_modele(monkeypatch):
    """Annoncer « aucun modèle installé » parce que le démon était arrêté
    enverrait l'exploitant télécharger ce qu'il possède déjà."""
    def faux_get(url, **kwargs):
        raise mod.http_requests.exceptions.ConnectionError()

    monkeypatch.setattr('apps.orion_ai.providers.http_requests.get', faux_get)

    assert mod.modeles_locaux_installes() == []


def test_les_modeles_presents_sont_nommes(monkeypatch):
    def faux_get(url, **kwargs):
        assert url.endswith('/api/tags')
        return _Reponse({'models': [
            {'model': 'qwen3.5:4b-q4_K_M'},
            {'name': 'qwen2.5:3b-instruct'},
            {},
        ]})

    monkeypatch.setattr('apps.orion_ai.providers.http_requests.get', faux_get)

    assert mod.modeles_locaux_installes() == [
        'qwen2.5:3b-instruct', 'qwen3.5:4b-q4_K_M']


# ─── Le nom du modèle, aux quatre endroits qui doivent s'accorder ────────────

def test_le_nom_par_defaut_est_un_tag_qwen3_5_qui_existe():
    """Les deux pièges du renommage, tenus ensemble.

    « qwen3.5:3b-instruct » passerait une relecture distraite : il ressemble à
    l'ancien nom. Il n'existe pas.
    """
    from apps.orion_ai.models import OrionAISettings

    nom = OrionAISettings._meta.get_field('default_model').default

    assert nom.startswith('qwen3.5:')
    assert '-instruct' not in nom, (
        'qwen3.5 n-a pas de suffixe -instruct : ce tag renverrait 404')
    assert not re.match(r'^qwen3\.5:3b\b', nom), (
        'qwen3.5 n-a pas de taille 3b : 0.8b, 2b, 4b, 9b')
    assert re.match(r'^qwen3\.5:(0\.8|2|4|9)b\b', nom), nom


def test_les_quatre_sources_du_nom_s_accordent():
    """Le script d'appliance, les réglages Django et le modèle de données
    nomment le même fichier.

    « les deux ont divergé une fois de trop dans ce projet », dit déjà
    orion-ai.sh à propos du modèle attendu. Un désaccord ici se solde par un
    téléchargement du mauvais modèle, puis un 404 à chaque question.
    """
    from django.conf import settings

    from apps.orion_ai.models import OrionAISettings

    attendu = OrionAISettings._meta.get_field('default_model').default

    assert settings.ORION_AI_DEFAULT_MODEL == attendu

    script = _lire(SCRIPT_IA)
    assert 'MODELE_DEFAUT="%s"' % attendu in script, (
        'orion-ai.sh ne telecharge pas le modele que l-application attend')

    migration = _lire(os.path.join(
        RACINE, 'apps', 'orion_ai', 'migrations',
        '0007_qwen3_5_et_reflexion.py'))
    assert attendu in migration


def test_le_modele_plus_petit_existe_aussi():
    """Le repli proposé quand le débit mesuré est trop faible. Il est cité à
    l'opérateur : un nom inexistant ferait échouer le téléchargement."""
    script = _lire(SCRIPT_IA)
    correspondance = re.search(r'MODELE_PLUS_PETIT="([^"]+)"', script)

    assert correspondance, 'le repli n-est plus defini'
    assert re.match(r'^qwen3\.5:(0\.8|2)b\b', correspondance.group(1)), (
        correspondance.group(1))


def test_plus_aucun_tag_qwen2_5_a_telecharger():
    """Un nom périmé cité dans un message d'aide envoie télécharger un modèle
    que l'application n'utilise plus.

    Ce sont les TAGS qui sont interdits (« qwen2.5:… », un nom de fichier à
    télécharger), pas la famille citée en prose : la documentation doit pouvoir
    expliquer ce qui a changé depuis qwen2.5, et les migrations gardent la
    valeur historique qu'elles ont écrite.
    """
    restes = []
    for chemin in (SCRIPT_IA, SCRIPT_VERIF,
                   os.path.join(RACINE, 'docs', 'ORION-IA.md')):
        for numero, ligne in enumerate(_lire(chemin).splitlines(), 1):
            if 'qwen2.5:' in ligne:
                restes.append('%s:%s' % (os.path.basename(chemin), numero))

    assert not restes, restes


# ─── Ce que le script d'appliance doit continuer de faire ───────────────────

def test_aucune_chaine_awk_ne_depasse_sa_ligne():
    """Le verdict de « bench » était coupé par de vrais retours à la ligne au
    milieu d'une chaîne awk — « unterminated string », et sous `set -e` le
    script s'arrêtait juste avant d'afficher la seule ligne que la
    documentation demande de lire. Mesuré, pas supposé : awk sortait en 1.
    """
    fautes = []
    for chemin in (SCRIPT_IA, SCRIPT_VERIF):
        for numero, ligne in enumerate(_lire(chemin).splitlines(), 1):
            if 'print "' in ligne and ligne.count('"') % 2:
                fautes.append('%s:%s' % (os.path.basename(chemin), numero))

    assert not fautes, fautes


def test_le_texte_d_aide_reste_complet():
    """La plage était écrite en dur (« sed -n 2,22p ») : toute ligne ajoutée
    à l'en-tête faisait disparaître la dernière ligne de l'aide, en silence.
    Elle est déduite — ce test garde le fait que l'aide atteint bien la fin
    de la liste des commandes."""
    script = _lire(SCRIPT_IA)

    assert "sed -n '2,22p'" not in script, (
        'la plage figee est revenue : elle se desynchronise a la premiere '
        'ligne ajoutee a l-en-tete')

    entete = []
    for ligne in script.splitlines()[1:]:
        if not ligne.startswith('#'):
            break
        entete.append(ligne)

    aide = '\n'.join(entete)
    for commande in ('install', 'status', 'test', 'bench', 'models', 'pull',
                     'stop | start'):
        assert 'orion-ai.sh %s' % commande in aide, commande


def _bash_utilisable():
    """Un `bash` dans le PATH ne prouve pas qu'un shell POSIX réponde.

    Sous Windows, `shutil.which('bash')` trouve `System32\\bash.exe`, le
    lanceur WSL — qui répond « pas de distribution à installer » en UTF-16 et
    sort en 1. Le test aurait alors échoué sur l'environnement, pas sur le
    script : un échec qui n'apprend rien et qu'on finit par ignorer.
    """
    if shutil.which('bash') is None:
        return False
    try:
        verdict = subprocess.run(
            ['bash', '-c', 'echo pret'], capture_output=True, text=True,
            timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return verdict.returncode == 0 and 'pret' in (verdict.stdout or '')


@pytest.mark.skipif(not _bash_utilisable(), reason='aucun shell POSIX')
def test_les_scripts_restent_syntaxiquement_valides():
    for chemin in (SCRIPT_IA, SCRIPT_VERIF):
        verdict = subprocess.run(
            ['bash', '-n', chemin], capture_output=True, text=True)
        assert verdict.returncode == 0, (chemin, verdict.stderr)


# ─── Réglable depuis l'interface, et non par la console ─────────────────────
# Les trois réglages de temps de réponse existaient dans le modèle, étaient
# transmis au moteur, et la documentation annonçait qu'on les trouvait dans
# « Paramètres IA » — mais aucun champ ne les portait. Ils n'étaient donc
# modifiables que par la console Django, ce qui revient à ne pas l'être.

def _super_admin(client, django_user_model):
    """Super-admin connecté, sur une base où l'installation est faite.

    La Company n'est pas décorative : `SetupRequiredMiddleware` redirige
    TOUTE adresse vers `/setup/` tant qu'aucune n'existe, et la page de
    réglages n'est alors jamais rendue — `response.context` vaut None et
    l'échec ne désigne pas sa cause. Mesuré sur ces cinq tests.
    """
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})

    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@x.fr')
    client.force_login(utilisateur)
    return utilisateur


def _formulaire(**remplacements):
    base = {
        'local_only': 'on',
        'default_provider': 'local',
        'default_model': MODELE,
        'ai_enabled': 'on',
        'ai_name': 'Orion',
        'system_prompt_extra': '',
        'keep_alive_minutes': '30',
        'max_output_tokens': '600',
        'context_window_tokens': '4096',
    }
    base.update(remplacements)
    return base


@pytest.mark.django_db
def test_la_reflexion_s_active_depuis_l_ecran(client, django_user_model):
    from django.urls import reverse

    from apps.orion_ai.models import OrionAISettings

    _super_admin(client, django_user_model)
    adresse = reverse('orion_ai:admin_ai_settings')

    client.post(adresse, _formulaire(local_thinking='on'))
    assert OrionAISettings.get_global().local_thinking is True

    # Une case décochée n'est pas postée : c'est ce qui l'éteint.
    client.post(adresse, _formulaire())
    assert OrionAISettings.get_global().local_thinking is False


@pytest.mark.django_db
def test_les_trois_reglages_de_temps_sont_enregistres(client,
                                                      django_user_model):
    from django.urls import reverse

    from apps.orion_ai.models import OrionAISettings

    _super_admin(client, django_user_model)

    client.post(reverse('orion_ai:admin_ai_settings'), _formulaire(
        keep_alive_minutes='45',
        max_output_tokens='900',
        context_window_tokens='8192',
    ))

    reglages = OrionAISettings.get_global()
    assert reglages.keep_alive_minutes == 45
    assert reglages.max_output_tokens == 900
    assert reglages.context_window_tokens == 8192


@pytest.mark.django_db
def test_un_nombre_illisible_conserve_le_reglage_en_place(client,
                                                          django_user_model):
    """La règle déjà posée dans cette vue pour le fournisseur : un champ qu'on
    ne comprend pas ne doit pas remplacer un réglage qui fonctionne."""
    from django.urls import reverse

    from apps.orion_ai.models import OrionAISettings

    _super_admin(client, django_user_model)
    adresse = reverse('orion_ai:admin_ai_settings')
    client.post(adresse, _formulaire(max_output_tokens='600'))

    for valeur in ('', 'beaucoup', '-5'):
        client.post(adresse, _formulaire(max_output_tokens=valeur))
        assert OrionAISettings.get_global().max_output_tokens == 600, valeur

    # Zéro, lui, est légitime : « aucun plafond ».
    client.post(adresse, _formulaire(max_output_tokens='0'))
    assert OrionAISettings.get_global().max_output_tokens == 0


@pytest.mark.django_db
def test_un_modele_absent_du_disque_est_signale(client, django_user_model,
                                                monkeypatch):
    """Le nom s'affichait, correctement orthographié, et rien ne disait
    qu'aucun fichier ne portait ce nom — alors que chaque question échouait."""
    from django.urls import reverse

    from apps.orion_ai.models import OrionAISettings

    reglages = OrionAISettings.get_global()
    reglages.default_provider = 'local'
    reglages.default_model = 'qwen3.5:9b'
    reglages.save()

    monkeypatch.setattr(
        'apps.orion_ai.providers.modeles_locaux_installes',
        lambda: ['qwen3.5:2b-q4_K_M', MODELE])

    _super_admin(client, django_user_model)
    reponse = client.get(reverse('orion_ai:admin_ai_settings'))

    assert reponse.context['modele_absent'] is True
    assert MODELE in reponse.context['modeles_presents']


@pytest.mark.django_db
def test_un_moteur_injoignable_ne_crie_pas_au_modele_manquant(
        client, django_user_model, monkeypatch):
    """« Je n'ai pas pu savoir » ne doit pas se présenter comme « il manque ».

    Sans cette distinction, un démon arrêté aurait affiché en rouge que le
    modèle n'est pas téléchargé, et envoyé l'exploitant retélécharger trois
    gigaoctets qu'il possède déjà.
    """
    from django.urls import reverse

    monkeypatch.setattr(
        'apps.orion_ai.providers.modeles_locaux_installes', lambda: [])

    _super_admin(client, django_user_model)
    reponse = client.get(reverse('orion_ai:admin_ai_settings'))

    assert reponse.context['modele_absent'] is False
