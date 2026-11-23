# -*- coding: utf-8 -*-
"""Les bandeaux de l'ERP, traduits selon la langue de l'interface.

**LE DÉFAUT MESURÉ (23/11/2026).** Les gabarits portent leurs `{% trans %}`
et se traduisent. Les **messages flash**, non : sur 721 appels à
`messages.success/error/warning/info`, **cinq** passaient par `gettext`. Une
interface en portugais servait donc des pages portugaises surmontées de
bandeaux français. Rien ne le signalait — un message s'affiche toujours,
simplement pas dans la bonne langue.

Détail : 327 appels portent un littéral (271 distincts), 315 sont des
f-strings qui insèrent une valeur, 79 passent une variable. **Zéro** des 271
littéraux ne figurait dans un catalogue.

**TROIS CHOIX QUE CES TESTS GARDENT.**

1. **La traduction est faite par le STOCKAGE, à la lecture.** Un filtre de
   gabarit aurait demandé de retoucher des dizaines d'endroits, et le
   premier oublié afficherait du français au milieu du portugais. À la
   lecture et non à l'écriture, parce qu'un message flash est écrit pendant
   une requête et lu pendant la suivante : c'est la langue de la page qui
   l'affiche qui doit décider.
2. **On dérive de `SessionStorage`**, que ce projet déclare, et non du
   `FallbackStorage` par défaut de Django. S'en écarter aurait fait repartir
   les messages en cookie quand la session est pleine — un changement de
   stockage glissé dans un changement de langue.
3. **Le moteur n'est JAMAIS appelé pendant un rendu.** Un modèle local à une
   seconde par chaîne ferait attendre cinq secondes une page portant cinq
   bandeaux. Les chaînes inconnues sont notées, puis traduites par lots.
"""
import pytest
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils.translation import override

from apps.core.models import Company

pytestmark = pytest.mark.django_db

HOTES = ['testserver']


# ═══════════════════════════════════════════════════════════════════════════
#  1. Le résolveur
# ═══════════════════════════════════════════════════════════════════════════

def test_le_francais_n_est_pas_touche():
    """La langue source est la majorité du trafic : on sort tout de suite.

    Et surtout, la traduire chercherait dans le catalogue une chaîne qui
    EST la source — donc noterait chaque message comme « à traduire ».
    """
    from apps.translations.messages_auto import traduire

    with override('fr'):
        assert traduire('Accès refusé.') == 'Accès refusé.'


@pytest.mark.parametrize('langue,attendu', [
    ('pt', 'Acesso recusado.'),
    ('de', 'Zugriff verweigert.'),
    ('en', 'Access denied.'),
    ('es', 'Acceso denegado.'),
    ('it', 'Accesso negato.'),
])
def test_un_message_du_catalogue_est_traduit(langue, attendu):
    """« Accès refusé. » paraît 33 fois dans le dépôt : le cas le plus vu."""
    from apps.translations.messages_auto import traduire

    with override(langue):
        assert traduire('Accès refusé.', noter=False) == attendu


@pytest.mark.parametrize('texte', ['', '   ', '42', '2026-11-23', '---'])
def test_ce_qui_n_a_rien_a_traduire_est_ecarte(texte):
    """Un nombre ou une date encombrerait le cache sans rien y gagner."""
    from apps.translations.messages_auto import traduisible

    assert traduisible(texte) is False


def test_un_texte_trop_long_n_est_pas_un_message():
    """Au-delà, c'est une trace d'exception ou une sortie de commande.

    Les faire passer au modèle coûterait du temps pour un texte que
    personne ne lit comme un bandeau.
    """
    from apps.translations.messages_auto import traduisible

    assert traduisible('a' * 401) is False
    assert traduisible('Message normal.') is True


def test_une_chaine_inconnue_est_rendue_en_francais_et_notee(db):
    """DEUX CHOSES À LA FOIS, et les deux comptent.

    Rendue en français : un bandeau dans la mauvaise langue vaut mieux que
    pas de bandeau. Notée : sans cela, il faudrait deviner la liste des
    chaînes à traduire — ou parcourir le code, ce qui ne verrait pas les
    315 f-strings.
    """
    from apps.translations.models import InterfaceTranslation, Language

    from apps.translations.messages_auto import traduire

    Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    inconnue = 'Ce message n’existe dans aucun catalogue, promis.'

    with override('pt'):
        assert traduire(inconnue) == inconnue

    ligne = InterfaceTranslation.objects.filter(
        source_text=inconnue, language__code='pt').first()
    assert ligne is not None, 'la chaîne inconnue n’a pas été notée'
    assert ligne.translated_text == '', (
        'une ligne notée doit rester VIDE : c’est elle qui dit « à faire »')
    assert ligne.module == 'messages'


def test_le_cache_est_employe_quand_le_catalogue_ne_sait_pas(db):
    """C'est par là que passent les f-strings, que le catalogue ne peut pas
    contenir : leur texte final n'existe qu'à l'exécution."""
    from apps.translations.messages_auto import _empreinte, traduire
    from apps.translations.models import InterfaceTranslation, Language

    langue, _c = Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    source = 'Utilisateur « Durand » créé.'
    InterfaceTranslation.objects.create(
        key=_empreinte(source), language=langue, company=None,
        source_text=source, translated_text='Utilizador « Durand » criado.',
        module='messages')

    with override('pt'):
        assert traduire(source) == 'Utilizador « Durand » criado.'


def test_une_ligne_de_cache_vide_ne_remplace_rien(db):
    """Une ligne notée mais pas encore traduite ne doit pas rendre « ».

    Sinon le bandeau s'afficherait VIDE — une panne qu'on mettrait
    longtemps à relier à la traduction.
    """
    from apps.translations.messages_auto import _empreinte, traduire
    from apps.translations.models import InterfaceTranslation, Language

    langue, _c = Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    source = 'Quelque chose de tout a fait inedit.'
    InterfaceTranslation.objects.create(
        key=_empreinte(source), language=langue, company=None,
        source_text=source, translated_text='', module='messages')

    with override('pt'):
        assert traduire(source) == source


def test_le_resolveur_ne_leve_jamais(db, monkeypatch):
    """Il est appelé pour chaque bandeau de chaque page.

    Une table absente avant migration, une base momentanément injoignable :
    rien de tout cela ne doit faire tomber la page qui voulait dire
    « Enregistré. »
    """
    from apps.translations import messages_auto

    def casse(*args, **kwargs):
        raise RuntimeError('base injoignable')

    monkeypatch.setattr(messages_auto, '_du_cache', casse)
    with override('pt'):
        with pytest.raises(RuntimeError):
            messages_auto._du_cache('x', 'pt')   # la panne est bien la

    # Et pourtant `traduire` doit tenir : il rattrape pour son compte.
    monkeypatch.setattr(messages_auto, '_du_cache', lambda *a, **k: None)
    monkeypatch.setattr(messages_auto, 'noter_a_traduire', casse)
    with override('pt'):
        assert messages_auto.traduire('Texte sans catalogue ni cache.') == \
            'Texte sans catalogue ni cache.'


# ═══════════════════════════════════════════════════════════════════════════
#  2. Le point de passage : le stockage
# ═══════════════════════════════════════════════════════════════════════════

def test_le_stockage_declare_derive_bien_de_session_storage():
    """PAS DU `FallbackStorage` DE DJANGO, et il fallait le vérifier.

    Ce projet déclare `SessionStorage` : les messages restent côté serveur.
    Dériver du défaut de Django les aurait fait repartir en cookie quand la
    session est pleine — un changement de stockage glissé dans un
    changement de langue.
    """
    from django.contrib.messages.storage.session import SessionStorage

    from apps.translations.message_storage import StockageTraduit

    assert issubclass(StockageTraduit, SessionStorage)


def test_le_stockage_est_celui_que_django_emploie():
    """Une classe parfaite que `MESSAGE_STORAGE` ne désigne pas ne traduit
    rien — c'est le motif que ce dépôt rencontre à chaque audit."""
    from django.conf import settings

    assert settings.MESSAGE_STORAGE == \
        'apps.translations.message_storage.StockageTraduit'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_bandeau_s_affiche_traduit_dans_la_page(client, db):
    """MESURÉ SUR LE HTML RENDU, de bout en bout.

    C'est le seul test qui prouve que la chaîne complète fonctionne : la
    vue pose le message, la redirection le stocke, et le gabarit l'affiche
    traduit sans avoir été modifié.
    """
    from apps.core import middleware
    from apps.translations.models import Language

    middleware._setup_complete_cache = None
    entreprise = Company.objects.create(name='Co', slug='co-messages')
    Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})

    utilisateur = User.objects.create_user(
        username='salarie-msg', email='s@msg.test', password='x')
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)

    session = client.session
    session['_language'] = 'pt'
    session.save()

    # `user_create` refuse un salarié ordinaire avec « Accès refusé. »,
    # puis redirige : exactement le parcours d'un bandeau.
    reponse = client.get(reverse('accounts:user_create'), follow=True)
    corps = reponse.content.decode()

    assert 'Acesso recusado.' in corps, (
        'le bandeau est resté en français : %s'
        % [str(m) for m in reponse.context['messages']])
    assert 'Accès refusé.' not in corps

    middleware._setup_complete_cache = None


# ═══════════════════════════════════════════════════════════════════════════
#  3. Le lot, et le verrou local
# ═══════════════════════════════════════════════════════════════════════════

def test_le_lot_force_le_fournisseur_local_en_dur():
    """LE POINT DE CONFIDENTIALITÉ, et ce n'est pas un réglage.

    Un message porte souvent un nom de client ou un numéro de facture.
    `get_ai_provider` sait refuser un fournisseur externe quand le verrou
    local est posé — mais ce verrou est un RÉGLAGE, et un réglage se change
    par inadvertance. Le lot passe donc `local_only=True` explicitement.
    """
    import ast
    import inspect

    from apps.translations import lot_de_traduction

    arbre = ast.parse(inspect.getsource(lot_de_traduction))
    appels = [n for n in ast.walk(arbre)
              if isinstance(n, ast.Call)
              and getattr(n.func, 'id', None) == 'get_ai_provider']
    assert appels, 'aucun appel au fournisseur : le test ne mesure rien'

    for appel in appels:
        mots = {k.arg: k.value for k in appel.keywords}
        assert 'local_only' in mots, 'un appel ne force pas le verrou local'
        assert getattr(mots['local_only'], 'value', None) is True
        premier = appel.args[0]
        assert getattr(premier, 'value', None) == 'local', (
            'un appel demande un fournisseur autre que local')


def _code_executable(module):
    """La source du module SANS commentaires ni docstrings.

    Une première version du test ci-dessous lisait la source telle quelle
    et échouait sur la docstring de `messages_auto`, qui RENVOIE vers
    `lot_de_traduction` pour expliquer où tourne le moteur. Une garde qui
    confond « le code fait ceci » et « le commentaire parle de ceci » pousse
    à retirer l'explication pour la faire taire — soit l'inverse du but.
    """
    import ast
    import inspect

    arbre = ast.parse(inspect.getsource(module))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.Module, ast.FunctionDef,
                                  ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        corps = noeud.body
        if (corps and isinstance(corps[0], ast.Expr)
                and isinstance(corps[0].value, ast.Constant)
                and isinstance(corps[0].value.value, str)):
            noeud.body = corps[1:] or [ast.Pass()]
    return ast.unparse(arbre)


def test_le_resolveur_n_appelle_jamais_le_moteur():
    """Il est sur le chemin de chaque rendu : un appel réseau y ferait
    attendre la page, et on désactiverait la traduction dans la semaine."""
    from apps.translations import messages_auto

    source = _code_executable(messages_auto)
    for interdit in ('get_ai_provider', 'requests', 'lot_de_traduction'):
        assert interdit not in source, (
            'messages_auto touche à %s : le moteur doit rester hors du '
            'chemin de rendu' % interdit)


@pytest.mark.parametrize('proposition,acceptee', [
    ('Acesso recusado.', True),
    ('', False),
    ('   ', False),
    ('Accès refusé.', False),                       # identique a la source
    ('Voici la traduction :\nAcesso recusado.', False),   # bavardage
    ('Bien sûr ! En portugais, on dirait « Acesso recusado », mais on peut '
     'aussi dire « Acesso negado » selon le contexte.', False),
])
def test_une_reponse_du_modele_est_verifiee(proposition, acceptee):
    """Un modèle local bavarde : il préfixe, explique, propose des variantes.

    Mieux vaut un bandeau français qu'un bandeau portant « Voici la
    traduction : ». Une réponse refusée laisse la chaîne en attente.
    """
    from apps.translations.lot_de_traduction import _reponse_acceptable

    accepte, _resultat = _reponse_acceptable('Accès refusé.', proposition)
    assert accepte is acceptee


def test_un_lot_sans_moteur_le_dit_au_lieu_de_pretendre(db, monkeypatch):
    """Un lot qui annoncerait « 25 traduits » sans moteur serait pire qu'un
    échec franc : on découvrirait les dégâts un bandeau à la fois."""
    from apps.orion_ai.providers import AIProviderError
    from apps.translations import lot_de_traduction
    from apps.translations.messages_auto import _empreinte
    from apps.translations.models import InterfaceTranslation, Language

    langue, _c = Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    InterfaceTranslation.objects.create(
        key=_empreinte('A traduire.'), language=langue, company=None,
        source_text='A traduire.', translated_text='', module='messages')

    def refuse(*args, **kwargs):
        raise AIProviderError('aucun modèle local joignable')

    monkeypatch.setattr('apps.orion_ai.providers.get_ai_provider', refuse)
    rapport = lot_de_traduction.traduire_un_lot(langue='pt')

    assert rapport['traduits'] == 0
    assert rapport['restants'] == 1
    assert 'local' in rapport['message'].lower()


def test_un_lot_enregistre_ce_que_le_modele_rend(db, monkeypatch):
    from apps.translations import lot_de_traduction
    from apps.translations.messages_auto import _empreinte
    from apps.translations.models import InterfaceTranslation, Language

    langue, _c = Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    ligne = InterfaceTranslation.objects.create(
        key=_empreinte('Devis enregistré.'), language=langue, company=None,
        source_text='Devis enregistré.', translated_text='',
        module='messages')

    class Faux:
        def generate(self, **kwargs):
            return {'content': 'Orçamento guardado.'}

    monkeypatch.setattr('apps.orion_ai.providers.get_ai_provider',
                        lambda *a, **k: Faux())
    rapport = lot_de_traduction.traduire_un_lot(langue='pt')

    ligne.refresh_from_db()
    assert rapport['traduits'] == 1
    assert ligne.translated_text == 'Orçamento guardado.'
    assert ligne.is_verified is False, (
        'une traduction de machine ne doit pas se déclarer vérifiée : '
        'l’exploitant doit distinguer ce qu’il a relu')


def test_un_lot_laisse_en_attente_ce_qu_il_refuse(db, monkeypatch):
    from apps.translations import lot_de_traduction
    from apps.translations.messages_auto import _empreinte
    from apps.translations.models import InterfaceTranslation, Language

    langue, _c = Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    ligne = InterfaceTranslation.objects.create(
        key=_empreinte('Devis enregistré.'), language=langue, company=None,
        source_text='Devis enregistré.', translated_text='',
        module='messages')

    class Bavard:
        def generate(self, **kwargs):
            return {'content': 'Bien sûr ! Voici plusieurs façons de le '
                               'dire en portugais, selon le registre '
                               'employé et le contexte de la phrase.'}

    monkeypatch.setattr('apps.orion_ai.providers.get_ai_provider',
                        lambda *a, **k: Bavard())
    rapport = lot_de_traduction.traduire_un_lot(langue='pt')

    ligne.refresh_from_db()
    assert ligne.translated_text == ''
    assert rapport['traduits'] == 0
    assert rapport['echecs'] == 1


# ═══════════════════════════════════════════════════════════════════════════
#  4. L'écran, sans terminal
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def exploitant(db, client):
    from apps.core import middleware

    middleware._setup_complete_cache = None
    entreprise = Company.objects.create(name='Co', slug='co-msg-ecran')
    utilisateur = User.objects.create_superuser(
        username='ops-msg', email='ops@msg.test', password='x')
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)
    yield client
    middleware._setup_complete_cache = None


@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_ecran_s_ouvre_et_annonce_le_verrou_local(exploitant):
    """L'écran existe pour que le lot ne soit pas une commande à taper.

    Et il doit dire que le moteur est local : c'est l'information dont
    l'exploitant a besoin pour savoir si des données sortent.
    """
    reponse = exploitant.get(reverse('translations_messages:etat'))
    corps = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'LOCAL' in corps or 'local' in corps
    assert 'quitte ce serveur' in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_lot_refuse_en_GET(exploitant):
    """Un GET qui appelle un modèle de langage partirait au survol d'un
    lien, et chaque passage coûterait du temps de calcul."""
    reponse = exploitant.get(reverse('translations_messages:lot'))
    assert reponse.status_code == 405


@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_ecran_est_reserve_au_superadmin(client, db):
    from apps.core import middleware

    middleware._setup_complete_cache = None
    entreprise = Company.objects.create(name='Co', slug='co-msg-refus')
    salarie = User.objects.create_user(
        username='salarie-ecran', email='s@msg.test', password='x')
    salarie.profile.companies.add(entreprise)
    salarie.profile.current_company = entreprise
    salarie.profile.save()
    client.force_login(salarie)

    reponse = client.get(reverse('translations_messages:etat'))
    assert reponse.status_code == 302
    assert reverse('translations_messages:etat') not in reponse['Location']

    middleware._setup_complete_cache = None


@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_ecran_liste_ce_qui_attend(exploitant, db):
    from apps.translations.messages_auto import _empreinte
    from apps.translations.models import InterfaceTranslation, Language

    langue, _c = Language.objects.get_or_create(
        code='pt', defaults={'name': 'Portugais', 'native_name': 'Português'})
    InterfaceTranslation.objects.create(
        key=_empreinte('Brouillon enregistré.'), language=langue,
        company=None, source_text='Brouillon enregistré.',
        translated_text='', module='messages')

    corps = exploitant.get(
        reverse('translations_messages:etat')).content.decode()
    assert 'Brouillon enregistré.' in corps
    assert 'Português' in corps
