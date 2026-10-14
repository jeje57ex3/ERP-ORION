"""Temps de réponse de l'assistant Orion.

Sur un petit modèle en CPU — le cas de l'appliance — le temps d'une réponse se
décompose en trois parts, et chacune a son remède :

  1. le **chargement** du modèle en mémoire. Ollama le décharge après un délai
     d'inactivité, et la question suivante attend qu'il remonte du disque.
     C'est ce qui rend l'assistant « parfois très lent » sans raison visible ;
  2. l'**évaluation du prompt**, proportionnelle à sa longueur. C'est elle qui
     fait ralentir une conversation à mesure qu'elle avance ;
  3. la **génération**, proportionnelle à la longueur de la réponse.

« Lent » ne dit pas laquelle des trois est en cause, et les trois remèdes sont
différents. Ces tests gardent donc à la fois les réglages et la **mesure** qui
permet de choisir.

Le défaut le plus coûteux était ailleurs, et invisible : la question partait en
double à chaque échange.
"""

import pytest

from apps.orion_ai.providers import LocalAIProvider

pytestmark = pytest.mark.django_db


class _Reponse:
    status_code = 200

    def __init__(self, donnees):
        self._donnees = donnees
        self.text = ''

    def json(self):
        return self._donnees


DUREES = {
    'message': {'content': 'Bonjour.'},
    'prompt_eval_count': 120,
    'eval_count': 40,
    'total_duration': 3_500_000_000,
    'load_duration': 2_000_000_000,
    'prompt_eval_duration': 500_000_000,
    'eval_duration': 1_000_000_000,
}


def _capturer(monkeypatch, donnees=None):
    """Remplace l'appel HTTP et retourne la charge réellement envoyée."""
    vu = {}

    def faux_post(url, **kwargs):
        vu['url'] = url
        vu['json'] = kwargs.get('json')
        return _Reponse(donnees if donnees is not None else DUREES)

    monkeypatch.setattr('apps.orion_ai.providers.http_requests.post', faux_post)
    return vu


# ── Garder le modèle en mémoire ──────────────────────────────────────────────

def test_le_modele_est_garde_en_memoire(monkeypatch):
    """Sans keep_alive, Ollama décharge le modèle après 5 minutes de calme :
    la question suivante attend plusieurs secondes son rechargement depuis le
    disque."""
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}],
        model='qwen2.5:3b-instruct',
        keep_alive_minutes=30,
    )
    assert vu['json']['keep_alive'] == '30m'


def test_la_duree_est_exprimee_en_minutes_et_non_en_secondes(monkeypatch):
    """Un entier nu est interprété en SECONDES par Ollama : « 30 » garderait
    le modèle une demi-minute au lieu d'une demi-heure, soit l'inverse de
    l'effet recherché."""
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'bonjour'}],
        model='m', keep_alive_minutes=30,
    )
    assert vu['json']['keep_alive'] != 30
    assert str(vu['json']['keep_alive']).endswith('m')


def test_zero_minute_decharge_aussitot(monkeypatch):
    """Réglage légitime sur une machine à mémoire serrée : il doit rester
    possible, et distinct de « non précisé »."""
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m',
        keep_alive_minutes=0,
    )
    assert vu['json']['keep_alive'] == 0


def test_sans_reglage_aucune_consigne_n_est_imposee(monkeypatch):
    """Le défaut d'Ollama doit rester le défaut si rien n'est demandé."""
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m')
    assert 'keep_alive' not in vu['json']


# ── Plafonner ce qui se paie en secondes ─────────────────────────────────────

def test_la_generation_est_plafonnee(monkeypatch):
    """Sans plafond, une réponse bavarde se paie en secondes d'attente."""
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m',
        max_output_tokens=600,
    )
    assert vu['json']['options']['num_predict'] == 600


def test_la_fenetre_de_contexte_est_bornee(monkeypatch):
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m',
        context_window_tokens=4096,
    )
    assert vu['json']['options']['num_ctx'] == 4096


def test_la_temperature_reste_transmise(monkeypatch):
    """Les ajouts de performance ne doivent pas évincer le réglage existant."""
    vu = _capturer(monkeypatch)
    LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m',
        temperature=0.4, max_output_tokens=100,
    )
    assert vu['json']['options']['temperature'] == pytest.approx(0.4)


# ── Mesurer, pour régler sur des chiffres ────────────────────────────────────

def test_les_trois_parts_du_temps_sont_mesurees(monkeypatch):
    """« Lent » ne dit pas s'il faut garder le modèle en mémoire, raccourcir
    le prompt ou plafonner la réponse."""
    _capturer(monkeypatch)
    resultat = LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m')

    mesures = resultat['timings']
    assert mesures['chargement_modele_ms'] == 2000
    assert mesures['evaluation_prompt_ms'] == 500
    assert mesures['generation_ms'] == 1000
    assert mesures['total_ms'] == 3500


def test_la_vitesse_de_generation_est_calculee(monkeypatch):
    """40 jetons en 1 s = 40 jetons/s : le chiffre qui dit si le modèle est
    adapté à la machine."""
    _capturer(monkeypatch)
    resultat = LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m')
    assert resultat['timings']['jetons_par_seconde'] == pytest.approx(40.0)


def test_des_mesures_absentes_ne_font_pas_echouer(monkeypatch):
    """Une version d'Ollama qui ne renvoie pas ces champs doit rester
    utilisable : la mesure est un confort, pas une dépendance."""
    _capturer(monkeypatch, {'message': {'content': 'ok'}})
    resultat = LocalAIProvider().generate(
        messages=[{'role': 'user', 'content': 'x'}], model='m')
    assert resultat['content'] == 'ok'
    assert resultat['timings']['generation_ms'] is None
    assert resultat['timings']['jetons_par_seconde'] is None


# ── Le défaut le plus coûteux : la question envoyée deux fois ───────────────

def _reglages():
    from apps.orion_ai.models import OrionAISettings
    return OrionAISettings.get_global()


def _conversation(entreprise=None):
    from apps.orion_ai.models import OrionAIConversation
    return OrionAIConversation.objects.create(company=entreprise)


def test_la_question_courante_n_est_pas_envoyee_deux_fois():
    """Elle est enregistrée en base AVANT la construction du prompt : sans
    exclusion, elle figurait dans l'historique puis était ajoutée une seconde
    fois en fin de liste. Des jetons payés pour rien à chaque échange, et un
    modèle qui voyait la demande répétée."""
    from apps.orion_ai.models import OrionAIMessage
    from apps.orion_ai.services import build_messages_for_provider

    conversation = _conversation()
    message = OrionAIMessage.objects.create(
        conversation=conversation, role='user', content='Où sont les devis ?')

    messages = build_messages_for_provider(
        conversation, _reglages(), 'Où sont les devis ?',
        exclure_message_id=message.pk,
    )

    questions = [
        m for m in messages
        if m['role'] == 'user' and m['content'] == 'Où sont les devis ?'
    ]
    assert len(questions) == 1, messages


def test_sans_exclusion_le_doublon_apparait():
    """Vérifie que le test ci-dessus éprouve bien quelque chose : sans
    l'exclusion, le doublon est là."""
    from apps.orion_ai.models import OrionAIMessage
    from apps.orion_ai.services import build_messages_for_provider

    conversation = _conversation()
    OrionAIMessage.objects.create(
        conversation=conversation, role='user', content='Où sont les devis ?')

    messages = build_messages_for_provider(
        conversation, _reglages(), 'Où sont les devis ?')
    questions = [
        m for m in messages
        if m['role'] == 'user' and m['content'] == 'Où sont les devis ?'
    ]
    assert len(questions) == 2


# ── Le budget de longueur de l'historique ───────────────────────────────────

def test_l_historique_est_borne_en_longueur():
    """C'est la LONGUEUR, non le nombre de messages, qui détermine le temps
    d'évaluation du prompt. Vingt messages courts coûtent moins que trois
    longs."""
    from apps.orion_ai.models import OrionAIMessage
    from apps.orion_ai.services import build_messages_for_provider

    conversation = _conversation()
    for index in range(6):
        OrionAIMessage.objects.create(
            conversation=conversation,
            role='user' if index % 2 == 0 else 'assistant',
            content='x' * 400,
        )

    reglages = _reglages()
    reglages.max_history_chars = 1000
    reglages.save()

    messages = build_messages_for_provider(
        conversation, reglages, 'question courante')

    anciens = [m for m in messages[1:] if m['content'] != 'question courante']
    total = sum(len(m['content']) for m in anciens)
    assert total <= 1000, total
    assert anciens, "l'historique ne doit pas être vidé entièrement"


def test_le_budget_garde_les_messages_les_plus_recents():
    """Ce sont eux qui portent le contexte utile."""
    from apps.orion_ai.models import OrionAIMessage
    from apps.orion_ai.services import build_messages_for_provider

    conversation = _conversation()
    for marqueur in ('ANCIEN', 'MILIEU', 'RECENT'):
        OrionAIMessage.objects.create(
            conversation=conversation, role='user',
            content=marqueur + 'y' * 400,
        )

    reglages = _reglages()
    reglages.max_history_chars = 500
    reglages.save()

    messages = build_messages_for_provider(
        conversation, reglages, 'question courante')
    contenus = ' '.join(m['content'] for m in messages)
    assert 'RECENT' in contenus
    assert 'ANCIEN' not in contenus


def test_un_budget_nul_ne_borne_pas_la_longueur():
    """Réglage légitime : certains exploitants préfèrent un historique
    complet, et leur machine peut le permettre."""
    from apps.orion_ai.models import OrionAIMessage
    from apps.orion_ai.services import build_messages_for_provider

    conversation = _conversation()
    for _ in range(4):
        OrionAIMessage.objects.create(
            conversation=conversation, role='user', content='z' * 500)

    reglages = _reglages()
    reglages.max_history_chars = 0
    reglages.save()

    messages = build_messages_for_provider(
        conversation, reglages, 'question courante')
    anciens = [m for m in messages[1:] if m['content'] != 'question courante']
    assert len(anciens) == 4


def test_un_seul_message_trop_long_n_est_pas_ecarte():
    """Écarter le seul message d'historique rendrait la conversation amnésique
    dès le premier échange un peu long."""
    from apps.orion_ai.models import OrionAIMessage
    from apps.orion_ai.services import build_messages_for_provider

    conversation = _conversation()
    OrionAIMessage.objects.create(
        conversation=conversation, role='user', content='w' * 5000)

    reglages = _reglages()
    reglages.max_history_chars = 100
    reglages.save()

    messages = build_messages_for_provider(
        conversation, reglages, 'question courante')
    anciens = [m for m in messages[1:] if m['content'] != 'question courante']
    assert len(anciens) == 1


# ── Les fournisseurs externes ne reçoivent pas ces réglages ─────────────────

def test_les_reglages_locaux_ne_sont_pas_passes_a_un_fournisseur_externe():
    """Ils lèveraient une TypeError. Un **kwargs complaisant serait pire : le
    réglage paraîtrait appliqué alors qu'il serait inerte."""
    import inspect

    from apps.orion_ai.providers import OpenAIProvider

    signature = inspect.signature(OpenAIProvider.generate)
    assert 'keep_alive_minutes' not in signature.parameters
    assert 'VAR_KEYWORD' not in str(
        [p.kind.name for p in signature.parameters.values()]
    )
