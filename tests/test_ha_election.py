"""Arbitrage de la bascule automatique : élection par quorum.

La bascule automatique décidait sur la seule vue du serveur qui l'exécute :
« je ne joins plus le principal, donc je prends la main ». Ce raisonnement est
juste quand le principal est tombé, et faux quand c'est le réseau qui s'est
coupé — or le serveur isolé ne peut pas distinguer les deux cas.

Lors d'une partition, chaque serveur isolé tenait donc ce raisonnement en même
temps : deux serveurs actifs, deux bases acceptant des écritures, et aucune
réconciliation automatique possible. C'est pourquoi la bascule automatique est
restée inopérante jusqu'ici.

**La propriété éprouvée ici est la sûreté de l'élection** : deux candidats ne
peuvent pas réunir chacun une majorité dans la même époque. Elle ne tient qu'à
deux conditions — une voix par serveur et par époque, persistée avant d'être
annoncée — et c'est ce que ces tests gardent. Le reste (refus expliqués,
drapeau par serveur, impossibilité à deux serveurs) sert à ce qu'un refus ne
passe pas pour une panne du mécanisme.
"""

import pytest

from apps.high_availability import election
from apps.high_availability.election import (
    accorder_une_voix,
    conduire_election,
    majorite,
)
from apps.high_availability.models import (
    OrionHAFailoverEvent,
    OrionHANode,
    OrionHASettings,
)

pytestmark = pytest.mark.django_db


def _serveur(identifiant, rang, actif=False, auto=True):
    return OrionHANode.objects.create(
        node_id=identifiant,
        name=identifiant,
        priority=rang,
        role='primary' if actif else 'secondary',
        status='active' if actif else 'passive',
        base_url='https://%s.exemple.fr' % identifiant,
        allow_auto_failover=auto,
        is_failover_target=not actif,
        # get_active_node() filtre sur CE champ, et non sur le role : sans lui,
        # la bascule automatique s'arretait sur « No active node » avant toute
        # election, et les tests passaient a cote de ce qu'ils visaient.
        is_current_active=actif,
    )


# ── La majorité ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize('total,attendu', [
    (1, 1), (2, 2), (3, 2), (4, 3), (5, 3), (6, 4), (7, 4),
])
def test_la_majorite_est_strictement_plus_de_la_moitie(total, attendu):
    """Jamais la moitié exacte : deux moitiés disjointes éliraient deux
    chefs, ce qui est précisément la divergence à exclure."""
    assert majorite(total) == attendu


def test_deux_majorites_se_recoupent_toujours():
    """Le fondement de la sûreté : deux majorités d'un même ensemble ont
    forcément un serveur en commun, et celui-ci n'a voté qu'une fois."""
    for total in range(1, 12):
        requis = majorite(total)
        assert 2 * requis > total, total


# ── Une voix par époque : la règle qui empêche la divergence ────────────────

def test_un_serveur_n_accorde_qu_une_voix_par_epoque():
    OrionHASettings.get_solo()

    premier = accorder_une_voix(
        epoque=7, candidat_id='serveur2', primaire_injoignable=True)
    assert premier['accordee'] is True

    # Un second candidat, même époque : refusé, sans quoi deux majorités
    # seraient possibles.
    second = accorder_une_voix(
        epoque=7, candidat_id='serveur3', primaire_injoignable=True)
    assert second['accordee'] is False
    assert 'serveur2' in second['raison']


def test_une_demande_reemise_par_le_meme_candidat_est_reconnue():
    """Réseau instable : la demande peut arriver deux fois. Elle ne doit pas
    être comptée deux fois, mais pas non plus refusée au candidat légitime."""
    OrionHASettings.get_solo()
    accorder_une_voix(epoque=4, candidat_id='serveur2',
                      primaire_injoignable=True)
    rappel = accorder_une_voix(epoque=4, candidat_id='serveur2',
                               primaire_injoignable=True)
    assert rappel['accordee'] is True
    assert rappel.get('deja') is True


def test_une_epoque_depassee_ne_defait_pas_un_vote_recent():
    OrionHASettings.get_solo()
    accorder_une_voix(epoque=9, candidat_id='serveur2',
                      primaire_injoignable=True)
    tardive = accorder_une_voix(epoque=5, candidat_id='serveur3',
                                primaire_injoignable=True)
    assert tardive['accordee'] is False
    assert 'dépassée' in tardive['raison']


def test_une_epoque_plus_recente_permet_un_nouveau_vote():
    """Sans cela, une élection ratée bloquerait définitivement la grappe."""
    OrionHASettings.get_solo()
    accorder_une_voix(epoque=3, candidat_id='serveur2',
                      primaire_injoignable=True)
    suivante = accorder_une_voix(epoque=4, candidat_id='serveur3',
                                 primaire_injoignable=True)
    assert suivante['accordee'] is True


def test_un_serveur_qui_joint_encore_le_principal_refuse():
    """Protège une grappe saine d'un serveur momentanément isolé."""
    OrionHASettings.get_solo()
    refus = accorder_une_voix(epoque=2, candidat_id='serveur2',
                              primaire_injoignable=False)
    assert refus['accordee'] is False
    assert 'joignable' in refus['raison']


def test_la_voix_est_persistee_avant_d_etre_annoncee():
    """Une voix annoncée puis perdue (coupure de courant) pourrait être
    accordée une seconde fois dans la même époque."""
    OrionHASettings.get_solo()
    accorder_une_voix(epoque=6, candidat_id='serveur2',
                      primaire_injoignable=True)
    reglages = OrionHASettings.objects.get(id=1)
    assert reglages.vote_epoch == 6
    assert reglages.vote_node_id == 'serveur2'
    assert reglages.vote_at is not None


@pytest.mark.parametrize('epoque', [0, -1, None, 'abc'])
def test_une_epoque_invalide_est_refusee(epoque):
    OrionHASettings.get_solo()
    assert accorder_une_voix(
        epoque=epoque, candidat_id='serveur2',
        primaire_injoignable=True)['accordee'] is False


def test_un_candidat_sans_identifiant_est_refuse():
    OrionHASettings.get_solo()
    assert accorder_une_voix(
        epoque=1, candidat_id='', primaire_injoignable=True)['accordee'] is False


# ── L'élection complète ──────────────────────────────────────────────────────

def _repondeur(voix_par_serveur):
    """Remplace l'appel réseau : chaque serveur répond selon la consigne."""
    def faux(serveur, epoque, candidat_id):
        accordee = voix_par_serveur.get(serveur.node_id, False)
        return {'accordee': accordee,
                'raison': 'test' if accordee else 'refus de test'}
    return faux


def test_une_majorite_elit_le_candidat(monkeypatch):
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)
    monkeypatch.setattr(election, '_demander_voix',
                        _repondeur({'serveur3': True}))

    resultat = conduire_election(candidat)
    assert resultat['elu'] is True
    assert resultat['voix'] == 2          # la sienne + serveur3
    assert resultat['voix_requises'] == 2
    assert resultat['total_serveurs'] == 3


def test_sans_majorite_aucune_bascule(monkeypatch):
    """Le serveur isolé : il vote pour lui-même, personne ne répond."""
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)
    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))

    resultat = conduire_election(candidat)
    assert resultat['elu'] is False
    assert resultat['voix'] == 1
    assert 'pas de majorité' in resultat['raison']


def test_deux_candidats_ne_peuvent_pas_gagner_la_meme_epoque():
    """LA propriété de sûreté, éprouvée là où elle vit : le vote.

    Chaque serveur tient sa propre comptabilité de vote, dans sa propre base.
    Le test la simule pour UN arbitre : sollicité par deux candidats dans la
    même époque, il n'en endosse qu'un. Deux majorités d'un même ensemble
    ayant forcément un serveur en commun, deux candidats ne peuvent donc pas
    gagner la même époque.
    """
    OrionHASettings.get_solo()

    pour_a = accorder_une_voix(epoque=5, candidat_id='serveur2',
                               primaire_injoignable=True)
    pour_b = accorder_une_voix(epoque=5, candidat_id='serveur3',
                               primaire_injoignable=True)

    assert pour_a['accordee'] is True
    assert pour_b['accordee'] is False, (
        'un arbitre a endossé deux candidats dans la même époque : '
        'deux majorités deviennent possibles'
    )


def test_des_elections_successives_sont_normales(monkeypatch):
    """Deux chefs élus dans des époques DIFFÉRENTES ne sont pas une anomalie :
    c'est une bascule, puis une autre. Ce que cela laisse ouvert — l'ancien
    chef isolé qui continue d'écrire — est fermé par la clôture, éprouvée plus
    bas, et non par l'élection."""
    _serveur('serveur1', 1, actif=True)
    candidat_a = _serveur('serveur2', 2)
    candidat_b = _serveur('serveur3', 3)
    monkeypatch.setattr(election, '_demander_voix',
                        _repondeur({'serveur2': True, 'serveur3': True}))

    premiere = conduire_election(candidat_a)
    seconde = conduire_election(candidat_b)
    assert premiere['epoque'] != seconde['epoque']


def test_a_deux_serveurs_la_bascule_automatique_est_refusee_explicitement():
    """Ce n'est pas une limite du code, c'est le théorème : à deux, rien ne
    distingue « l'autre est mort » de « je suis isolé ». Le dire vaut mieux
    que l'ignorer en silence."""
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)

    resultat = conduire_election(candidat)
    assert resultat['elu'] is False
    assert 'impossible' in resultat['raison']
    assert 'troisième' in resultat['raison']


def test_l_epoque_est_strictement_croissante(monkeypatch):
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)
    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))

    premiere = conduire_election(candidat)['epoque']
    seconde = conduire_election(candidat)['epoque']
    assert seconde > premiere


def test_le_candidat_vote_pour_lui_meme_et_cela_est_persiste(monkeypatch):
    """Sans cette persistance, il pourrait voter pour un autre candidat dans
    la même époque, et deux majorités redeviendraient possibles."""
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)
    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))

    resultat = conduire_election(candidat)
    reglages = OrionHASettings.objects.get(id=1)
    assert reglages.vote_node_id == 'serveur2'
    assert reglages.vote_epoch == resultat['epoque']


def test_un_serveur_injoignable_ne_compte_pas_pour_le_candidat(monkeypatch):
    """Une panne réseau ne doit pas valoir un accord : elle doit bloquer."""
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    def injoignable(serveur, epoque, candidat_id):
        return {'accordee': False, 'raison': 'Injoignable (ConnectionError).'}

    monkeypatch.setattr(election, '_demander_voix', injoignable)
    assert conduire_election(candidat)['elu'] is False


def test_le_denominateur_est_le_nombre_de_serveurs_declares(monkeypatch):
    """Calculer la majorité sur les seuls serveurs JOIGNABLES permettrait à un
    serveur isolé de former à lui seul « la majorité » de ce qu'il voit."""
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)
    _serveur('serveur4', 4)
    _serveur('serveur5', 5)
    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))

    resultat = conduire_election(candidat)
    assert resultat['total_serveurs'] == 5
    assert resultat['voix_requises'] == 3


# ── La bascule automatique qui s'appuie dessus ───────────────────────────────

def _reglages_permissifs():
    reglages = OrionHASettings.get_solo()
    reglages.failover_enabled = True
    reglages.automatic_failover_enabled = True
    reglages.require_manual_confirmation = False
    reglages.save()
    return reglages


def test_la_bascule_automatique_exige_la_majorite(monkeypatch):
    from apps.high_availability import automatic

    _reglages_permissifs()
    actif = _serveur('serveur1', 1, actif=True)
    actif.status = 'down'
    actif.save()
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))
    appels = []
    monkeypatch.setattr(
        automatic, 'run_manual_failover_to_node',
        lambda **kwargs: appels.append(kwargs),
    )

    resultat = automatic.check_and_run_automatic_failover()
    assert resultat.get('skipped') is True
    assert appels == [], 'bascule effectuée sans majorité'


def test_un_refus_est_journalise(monkeypatch):
    """Une bascule qui ne se produit pas, sans que rien ne dise pourquoi, est
    aussi gênante qu'une bascule à tort : on ne sait pas si le mécanisme a
    jugé ou s'il dort."""
    from apps.high_availability import automatic

    _reglages_permissifs()
    actif = _serveur('serveur1', 1, actif=True)
    actif.status = 'down'
    actif.save()
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))
    monkeypatch.setattr(
        automatic, 'run_manual_failover_to_node', lambda **kwargs: None)

    automatic.check_and_run_automatic_failover()
    evenement = OrionHAFailoverEvent.objects.filter(status='refused').first()
    assert evenement is not None, (
        'aucun refus journalisé : un « except Exception: pass » avait déjà '
        'avalé une erreur de nom de champ ici, rendant le mécanisme muet'
    )
    assert 'majorité' in evenement.reason
    # Le candidat écarté doit être nommé : « pas de majorité » sans dire pour
    # qui n'aide pas à comprendre.
    assert evenement.to_node is not None
    assert evenement.to_node.node_id == 'serveur2'
    # Et le détail des voix, pour savoir QUI n'a pas répondu.
    assert 'serveur3' in evenement.reason


def test_la_bascule_automatique_consulte_le_drapeau_de_chaque_serveur(monkeypatch):
    """`select_best_failover_target()` était appelé sans `automatic=True` : la
    case « promotion automatique autorisée » n'était pas lue, et un serveur
    explicitement exclu pouvait être choisi."""
    from apps.high_availability import automatic

    _reglages_permissifs()
    actif = _serveur('serveur1', 1, actif=True)
    actif.status = 'down'
    actif.save()
    # Les deux candidats possibles refusent la promotion automatique.
    _serveur('serveur2', 2, auto=False)
    _serveur('serveur3', 3, auto=False)

    appels = []
    monkeypatch.setattr(
        automatic, 'run_manual_failover_to_node',
        lambda **kwargs: appels.append(kwargs),
    )

    resultat = automatic.check_and_run_automatic_failover()
    assert resultat.get('skipped') is True
    assert appels == []


def test_une_majorite_declenche_bien_la_bascule(monkeypatch):
    """Le mécanisme doit aussi fonctionner : un garde-fou qui bloque tout
    serait indiscernable d'une panne."""
    from apps.high_availability import automatic

    _reglages_permissifs()
    actif = _serveur('serveur1', 1, actif=True)
    actif.status = 'down'
    actif.save()
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    monkeypatch.setattr(election, '_demander_voix',
                        _repondeur({'serveur3': True}))

    class _Evenement:
        id = 42

    appels = []

    def faux_failover(**kwargs):
        appels.append(kwargs)
        return _Evenement()

    monkeypatch.setattr(
        automatic, 'run_manual_failover_to_node', faux_failover)

    resultat = automatic.check_and_run_automatic_failover()
    assert resultat.get('ok') is True
    assert len(appels) == 1
    assert appels[0]['target_node'].node_id == 'serveur2'


# ── Clôture du serveur actif privé de majorité ───────────────────────────────
# L'élection empêche une minorité d'élire un chef. Elle n'empêche pas le chef
# DÉJÀ en place, isolé du mauvais côté d'une coupure, de continuer d'écrire
# pendant que la majorité en élit un autre. C'est la divergence par un autre
# chemin, et c'est ce que ces tests gardent fermé.

def _ce_serveur(monkeypatch, identifiant):
    monkeypatch.setattr(election, 'identifiant_local', lambda: identifiant)


def test_l_actif_prive_de_majorite_est_cloture(monkeypatch):
    from apps.high_availability.election import verifier_quorum_local

    _ce_serveur(monkeypatch, 'serveur1')
    _serveur('serveur1', 1, actif=True)
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    # Les deux autres sont injoignables : l'actif ne voit que lui-même.
    resultats = [
        {'node': OrionHANode.objects.get(node_id='serveur1'), 'ok': True},
        {'node': OrionHANode.objects.get(node_id='serveur2'), 'ok': False},
        {'node': OrionHANode.objects.get(node_id='serveur3'), 'ok': False},
    ]
    bilan = verifier_quorum_local(resultats)

    assert bilan['applicable'] is True
    assert bilan['quorum_perdu'] is True
    assert bilan['vus'] == 1 and bilan['requis'] == 2
    assert OrionHASettings.objects.get(id=1).quorum_perdu is True


def test_la_cloture_est_levee_au_retour_de_la_majorite(monkeypatch):
    from apps.high_availability.election import verifier_quorum_local

    _ce_serveur(monkeypatch, 'serveur1')
    _serveur('serveur1', 1, actif=True)
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    reglages = OrionHASettings.get_solo()
    reglages.quorum_perdu = True
    reglages.save()

    resultats = [
        {'node': OrionHANode.objects.get(node_id='serveur1'), 'ok': True},
        {'node': OrionHANode.objects.get(node_id='serveur2'), 'ok': True},
        {'node': OrionHANode.objects.get(node_id='serveur3'), 'ok': False},
    ]
    bilan = verifier_quorum_local(resultats)

    assert bilan['quorum_perdu'] is False
    assert OrionHASettings.objects.get(id=1).quorum_perdu is False
    assert OrionHASettings.objects.get(id=1).quorum_perdu_depuis is None


def test_un_serveur_non_actif_n_est_pas_cloture(monkeypatch):
    """Il n'a rien à clôturer : l'intergiciel lui refuse déjà les écritures."""
    from apps.high_availability.election import verifier_quorum_local

    _ce_serveur(monkeypatch, 'serveur2')
    _serveur('serveur1', 1, actif=True)
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    bilan = verifier_quorum_local([])
    assert bilan['applicable'] is False
    assert OrionHASettings.objects.get(id=1).quorum_perdu is False


def test_a_deux_serveurs_la_cloture_ne_s_applique_pas(monkeypatch):
    """Le remède serait pire que le mal : une simple coupure du lien rendrait
    inutilisable le seul serveur qui fonctionne."""
    from apps.high_availability.election import verifier_quorum_local

    _ce_serveur(monkeypatch, 'serveur1')
    _serveur('serveur1', 1, actif=True)
    _serveur('serveur2', 2)

    resultats = [
        {'node': OrionHANode.objects.get(node_id='serveur1'), 'ok': True},
        {'node': OrionHANode.objects.get(node_id='serveur2'), 'ok': False},
    ]
    bilan = verifier_quorum_local(resultats)
    assert bilan['applicable'] is False
    assert OrionHASettings.objects.get(id=1).quorum_perdu is False


def test_une_protection_levee_n_est_pas_reimposee(monkeypatch):
    """Qui a explicitement levé la protection anti-divergence a décidé : on ne
    la réimpose pas par un autre biais."""
    from apps.high_availability.election import verifier_quorum_local

    _ce_serveur(monkeypatch, 'serveur1')
    _serveur('serveur1', 1, actif=True)
    _serveur('serveur2', 2)
    _serveur('serveur3', 3)

    reglages = OrionHASettings.get_solo()
    reglages.split_brain_protection_enabled = False
    reglages.quorum_perdu = True
    reglages.save()

    bilan = verifier_quorum_local([])
    assert bilan['applicable'] is False
    assert OrionHASettings.objects.get(id=1).quorum_perdu is False


def test_l_intergiciel_refuse_les_ecritures_sous_cloture():
    """La clôture ne vaut que si quelque chose la fait respecter."""
    import io as _io
    import os
    from django.conf import settings as djsettings

    chemin = os.path.join(djsettings.BASE_DIR, 'apps', 'high_availability',
                          'middleware.py')
    with _io.open(chemin, encoding='utf-8') as fichier:
        code = fichier.read()
    assert 'quorum_perdu' in code
    # Et le point d'entrée du vote doit rester joignable : il est adressé à des
    # serveurs NON actifs par définition, et il écrit.
    assert "'/ha/vote/'" in code


def test_un_serveur_desactive_ne_compte_pas_dans_la_majorite(monkeypatch):
    """Un serveur désactivé est retiré de la grappe par décision de
    l'exploitant : le balayage ne l'interroge plus et il ne peut plus recevoir
    la main. Exiger sa voix clôturerait définitivement une grappe
    légitimement réduite — par exemple ramenée de trois serveurs à un seul."""
    from apps.high_availability.election import verifier_quorum_local

    _ce_serveur(monkeypatch, 'serveur1')
    _serveur('serveur1', 1, actif=True)
    retire = _serveur('serveur2', 2)
    retire.is_enabled = False
    retire.save()
    autre_retire = _serveur('serveur3', 3)
    autre_retire.is_enabled = False
    autre_retire.save()

    bilan = verifier_quorum_local([
        {'node': OrionHANode.objects.get(node_id='serveur1'), 'ok': True},
    ])
    # Un seul serveur dans la grappe : la clôture ne s'applique pas, et
    # surtout l'actif n'est pas verrouillé.
    assert bilan['applicable'] is False
    assert OrionHASettings.objects.get(id=1).quorum_perdu is False


def test_la_majorite_se_calcule_sur_les_serveurs_actifs_de_la_grappe(monkeypatch):
    _serveur('serveur1', 1, actif=True)
    candidat = _serveur('serveur2', 2)
    _serveur('serveur3', 3)
    quatrieme = _serveur('serveur4', 4)
    quatrieme.is_enabled = False
    quatrieme.save()

    monkeypatch.setattr(election, '_demander_voix', _repondeur({}))
    resultat = conduire_election(candidat)
    # Trois serveurs participent, pas quatre : deux voix suffisent.
    assert resultat['total_serveurs'] == 3
    assert resultat['voix_requises'] == 2
