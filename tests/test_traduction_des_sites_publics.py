# -*- coding: utf-8 -*-
"""« Le système de traduction ne traduit pas tout sur le site Sparkling Peace. »

TROIS CAUSES SUPERPOSÉES, ET LA DEUXIÈME TOUCHAIT TOUTES LES LANGUES.

**1. Je travaillais sur les mauvais gabarits.** `s-peace.com` est la
vitrine ÉLECTRICITÉ — `templates/websites/public/electricite/`, 216 chaînes
traduisibles. Au tour précédent j'avais complété les 48 chaînes de la
vitrine ÉTANCHÉITÉ, que ce site ne rend jamais. Mesuré ensuite : 32 chaînes
absentes des catalogues anglais, espagnol et portugais, et 161 de
l'allemand.

**2. Le contenu statique n'avait aucune traduction en base.** Les noms de
services et la foire aux questions ne viennent pas des gabarits : ce sont
des listes Python, passées par `translate_static_items`, qui lit
`InterfaceTranslation` — donc la BASE — et retombe sur le français quand
rien n'existe. Or seul `manage.py seed_site_translations` créait ces
lignes, **un fichier qui n'était pas suivi par git**. Il n'existait donc
pas sur le serveur. Résultat : les noms de services et la FAQ, c'est-à-dire
l'essentiel du contenu visible d'une page d'accueil, restaient en français
DANS TOUTES LES LANGUES. Troisième défaut de cette famille dans ce dépôt :
un fichier non versionné dont dépend une fonctionnalité qui, elle, l'est.

**3. L'allemand n'était nulle part.** Ni dans les catalogues de ce site, ni
dans le contenu statique — la commande non suivie ne portait que
en/es/it/pt.

CE QUI N'EST PAS CORRIGÉ, ET C'EST DIT DANS UN TEST PLUTÔT QUE TAIRE : la
vitrine BTP, qui est un AUTRE site, n'a que 50 de ses 205 chaînes en
allemand. Elle est complète en anglais, espagnol et portugais.
"""
import io
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(RACINE, 'templates', 'websites', 'public')
LANGUES = ('en', 'es', 'pt', 'de')

TRANS = re.compile(r"""\{%\s*(?:trans|translate)\s+(["'])(.+?)\1""", re.S)


def _chaines(famille):
    """Les chaînes traduisibles d'une famille de gabarits.

    Lues sur les GABARITS, jamais sur un catalogue : c'est le code qui dit
    ce qui doit être traduit, et une liste tirée du catalogue ne pourrait
    jamais révéler un manque.
    """
    dossier = BASE if famille == '' else os.path.join(BASE, famille)
    chaines = set()
    for courant, _sous, fichiers in os.walk(dossier):
        if famille == '' and os.path.relpath(courant, BASE) != '.':
            continue
        for nom in sorted(fichiers):
            if not nom.endswith('.html'):
                continue
            contenu = io.open(os.path.join(courant, nom), encoding='utf-8',
                              errors='replace').read()
            for _quote, texte in TRANS.findall(contenu):
                chaines.add(texte.strip())
    return chaines


def _traduites(langue):
    """Les msgid RENSEIGNÉS du catalogue d'une langue.

    `polib` et non une recherche de texte : un `msgid` replié sur plusieurs
    lignes échappe à un `grep`, et c'est ainsi qu'une première mesure a
    surestimé les absences de dix-huit chaînes.
    """
    import polib

    chemin = os.path.join(RACINE, 'locale', langue, 'LC_MESSAGES',
                          'django.po')
    catalogue = polib.pofile(chemin)
    return {entree.msgid for entree in catalogue if entree.msgstr.strip()}


#: Les familles qui doivent être complètes dans les quatre langues.
#: « electricite » est celle du site Sparkling Peace.
FAMILLES_COMPLETES = ['', 'components', 'electricite', 'etancheite',
                      'partials']


@pytest.mark.parametrize('famille', FAMILLES_COMPLETES)
@pytest.mark.parametrize('langue', LANGUES)
def test_chaque_famille_de_gabarits_est_entierement_traduite(famille,
                                                             langue):
    """LA GARDE QUI COMPTE.

    Une chaîne sans traduction retombe sur le français : la page s'affiche,
    aucune erreur n'est levée, et le visiteur lit un site à moitié traduit.
    Personne ne relit deux cents chaînes dans quatre langues — c'est
    exactement le genre de défaut qu'un test doit porter.
    """
    chaines = _chaines(famille)
    assert chaines, 'aucune chaine trouvee : ce test ne garderait rien.'

    absentes = sorted(chaines - _traduites(langue))

    assert not absentes, (
        '%d chaine(s) de « %s » absente(s) du catalogue %s. Elles '
        'retomberont sur le francais, sans erreur :\n  %s'
        % (len(absentes), famille or 'generiques', langue,
           '\n  '.join(absentes[:12])))


def test_le_site_sparkling_peace_est_le_site_electricite():
    """Pour que personne ne complète encore la mauvaise famille.

    Je l'ai fait deux fois : d'abord les gabarits génériques, puis
    l'étanchéité. La vitrine de `s-peace.com` est celle d'électricité, et
    elle compte quatre fois plus de chaînes que l'étanchéité — 216 contre
    48. Compléter la mauvaise donne un travail juste et sans effet.
    """
    assert len(_chaines('electricite')) > len(_chaines('etancheite'))
    assert 'electricite' in FAMILLES_COMPLETES


#: La vitrine BTP est un AUTRE site. Son allemand est incomplet, et c'est
#: écrit ici plutôt que passé sous silence : le chiffre se lit, et le jour
#: où quelqu'un le complète, ce test le lui dira.
BTP_ALLEMAND_INCOMPLET = True


@pytest.mark.parametrize('langue', ['en', 'es', 'pt'])
def test_la_vitrine_btp_est_traduite_sauf_en_allemand(langue):
    """Elle est complète dans les trois autres langues."""
    absentes = sorted(_chaines('btp') - _traduites(langue))
    assert not absentes, (
        '%d chaine(s) de la vitrine BTP absente(s) de %s :\n  %s'
        % (len(absentes), langue, '\n  '.join(absentes[:12])))


def test_le_manque_allemand_de_la_vitrine_btp_est_connu():
    """On nomme ce qui reste, au lieu de le taire.

    Si quelqu'un complète l'allemand de la vitrine BTP, ce test échoue et
    l'invite à retirer l'exception — plutôt que de laisser croire qu'un
    manque documenté est un manque voulu.
    """
    manquantes = _chaines('btp') - _traduites('de')
    assert manquantes, (
        'la vitrine BTP est maintenant traduite en allemand : retirez cette '
        'exception et ajoutez « btp » a FAMILLES_COMPLETES.')


@pytest.mark.parametrize('langue', LANGUES)
def test_aucun_fragment_n_a_ete_pose_comme_cle(langue):
    """UN DÉFAUT QUE J'AI INTRODUIT ET QUI AURAIT PU PASSER.

    Les chaînes de ces gabarits portent accents et apostrophes
    typographiques, et je les désigne par des FRAGMENTS pour ne pas les
    recopier. Un script a cherché le msgid complet parmi les entrées du
    catalogue — or pour une chaîne ABSENTE du catalogue, précisément le cas
    à traiter, la recherche ne rend rien, et il a posé le fragment
    lui-même : « timent à votre service. ».

    L'entrée ne correspondait à aucune chaîne du code, et la vraie restait
    non traduite. Un fragment sert à DÉSIGNER une chaîne qu'on a par
    ailleurs ; il n'est jamais la chaîne.
    """
    import polib

    chemin = os.path.join(RACINE, 'locale', langue, 'LC_MESSAGES',
                          'django.po')
    catalogue = polib.pofile(chemin)

    # Un msgid qui commence au milieu d'un mot français est le signe sûr
    # d'un fragment pris pour une clé.
    suspects = [entree.msgid for entree in catalogue
                if entree.msgid.startswith(('timent ', 'quipe ', 'couvrir ',
                                            'sentation', 'durabilit',
                                            'activit '))]

    assert not suspects, (
        'des fragments ont ete poses comme cles de traduction : %s'
        % suspects)


# ═══ LE CONTENU STATIQUE, QUI VIENT DE LA BASE ══════════════════════════════

@pytest.mark.django_db
def test_le_contenu_statique_est_traduit_en_base():
    """LA CAUSE QUI TOUCHAIT TOUTES LES LANGUES.

    Les noms de services et la FAQ sont des listes Python, traduites par
    `translate_static_items` qui lit `InterfaceTranslation`. Rien ne créait
    ces lignes sinon une commande dont le fichier n'était pas suivi par
    git : sur le serveur, elles n'existaient pas, et tout retombait sur le
    français quelle que soit la langue choisie.

    La migration `translations/0005_contenu_statique_des_sites` les pose
    désormais, depuis un module versionné.
    """
    from apps.translations.models import InterfaceTranslation

    lignes = InterfaceTranslation.objects.filter(
        company=None, key__startswith='electricite.service.')
    assert lignes.exists(), (
        'aucune traduction de service en base : le contenu statique du '
        'site restera en francais dans toutes les langues.'
    )

    codes = set(lignes.values_list('language__code', flat=True))
    assert {'en', 'es', 'pt', 'de'} <= codes, (
        'langues manquantes pour le contenu statique : %s'
        % sorted({'en', 'es', 'pt', 'de'} - codes))


@pytest.mark.django_db
def test_un_nom_de_service_sort_en_allemand():
    """Mesuré sur le RÉSULTAT, et non sur la présence de lignes en base.

    C'est la plainte elle-même : le visiteur allemand lisait « Domotique »
    sous un titre allemand.
    """
    from django.utils import translation

    from apps.websites.electricite_public_views import ELECTRICITE_SERVICES
    from apps.websites.public_views import translate_static_items

    with translation.override('de'):
        services = translate_static_items(ELECTRICITE_SERVICES,
                                          'electricite.service')
        par_slug = {service['slug']: service for service in services}

    assert par_slug['domotique']['name'] == 'Gebäudeautomation'
    assert par_slug['electricite-generale']['name'] == 'Elektroinstallation'


@pytest.mark.django_db
def test_la_faq_sort_en_allemand():
    from django.utils import translation

    from apps.websites.electricite_public_views import FAQ_ITEMS
    from apps.websites.public_views import translate_faq_items

    with translation.override('de'):
        items = translate_faq_items(FAQ_ITEMS, 'electricite.faq')

    assert items, 'aucune entree de FAQ'
    questions = [question for question, _reponse in items]
    assert any('Noteinsätze' in question for question in questions), questions


@pytest.mark.django_db
def test_le_francais_n_est_pas_declare_en_base():
    """Il est la SOURCE, dans le code des vues.

    Déclarer des lignes « fr » dupliquerait la source, et les deux
    finiraient par diverger — on corrigerait le texte dans la vue et
    l'écran continuerait d'afficher l'ancien.
    """
    from apps.translations.models import InterfaceTranslation

    assert not InterfaceTranslation.objects.filter(
        company=None, key__startswith='electricite.',
        language__code='fr').exists()


def test_le_module_de_contenu_est_versionne():
    """Le défaut d'origine : il ne l'était pas.

    `seed_site_translations.py` n'était pas suivi par git, donc le serveur
    ne l'avait jamais. Les données vivent maintenant dans un module du
    dépôt, et une migration les pose — sans terminal, ce que les règles de
    ce projet exigent pour un réglage d'exploitation.
    """
    import subprocess

    resultat = subprocess.run(
        ['git', 'ls-files', 'apps/translations/contenu_des_sites.py'],
        cwd=RACINE, capture_output=True, text=True)
    if resultat.returncode != 0:
        pytest.skip('git indisponible ici.')

    assert resultat.stdout.strip(), (
        'apps/translations/contenu_des_sites.py n-est pas dans le depot : '
        'la migration qui le lit echouera sur le serveur.')
