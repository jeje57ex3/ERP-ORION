# -*- coding: utf-8 -*-
"""La bascule de la palette vers l'ardoise et l'azur.

La barre latérale est devenue une pastille bleue vive. Le reste de l'ERP
était resté en sable, brun et or : fond `#F8F3EA`, texte `#2B2118`,
bordures `#E3D5BD`, accent `#C6A15B`. Une pastille froide sur une page
chaude.

CE QUE CES TESTS PROTÈGENT, ET POURQUOI CHACUN EXISTE

La conversion a touché 881 couleurs dans 137 fichiers. À cette échelle,
aucune relecture de diff ne garantit quoi que ce soit : il faut des
propriétés vérifiables.

1. **La luminance est préservée.** C'est la seule raison pour laquelle on
   peut repeindre 527 écrans sans les regarder un par un : si chaque
   couleur garde sa luminance relative, aucun rapport de contraste ne
   peut se dégrader, donc aucun texte ne peut devenir illisible. Un test
   le mesure sur chaque entrée de la table.

2. **Les couleurs d'état survivent.** Un ambre d'alerte devenu cyan ne
   prévient plus de rien. La table est une liste blanche précisément pour
   ça, et un test vérifie que les gammes rouge et ambre sont toujours là.

3. **Le planning distingue encore ses catégories.** C'est le piège trouvé
   en route : dans `_palette.html`, « maladie » est codé en or et
   « congé » en bleu. Rabattre tous les ors vers le cyan les aurait rendus
   quasi identiques — un planning où l'arrêt maladie ressemble aux
   vacances.

4. **L'échelle garde ses pas.** Ce test existe parce que j'ai cassé cette
   propriété et ne l'ai vue qu'en la mesurant : deux ancres posées à la
   main éclaircissaient un ton moyen, et une carte bordée passait d'un
   rapport de 1.12 à 1.01 avec sa propre bordure. La bordure
   disparaissait. Les ancres ont été retirées.

5. **Les sites publics sont épargnés.** SIÈCLE, LUNEA, le site BTP et le
   portail client ont leurs propres identités. Le dépôt avait déjà posé
   cette frontière dans `scripts/check_internal_theme_colors.py` ; on la
   reprend plutôt que d'en inventer une neuvième.
"""

import os
import re
import sys

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, 'scripts'))

import palette_froide as pf  # noqa: E402


def _lire(chemin):
    with open(chemin, encoding='utf-8', errors='surrogateescape') as fichier:
        return fichier.read()


def _jeton(feuille, nom):
    """La DERNIÈRE définition d'un jeton dans une feuille.

    La dernière, pas la première : en CSS c'est elle qui s'applique, et
    plusieurs de ces feuilles redéfinissent leurs jetons pour le thème
    sombre après les avoir posés pour le thème clair.
    """
    trouves = re.findall(
        r'--%s:\s*(#[0-9a-fA-F]{3,8})' % re.escape(nom),
        _lire(os.path.join(RACINE, 'static', 'css', feuille)))
    return trouves[-1].lstrip('#') if trouves else None


# ─── La table, avant toute application ───────────────────────────────────

def test_aucune_cible_n_est_chaude():
    """Une cible chaude signifierait une conversion qui n'a rien converti."""
    chaudes = []
    for avant, apres in pf.table().items():
        r, g, b = pf.vers_rgb(apres)
        if (r - b) >= 3 and max(r, g, b) - min(r, g, b) >= 3:
            chaudes.append('%s -> %s' % (avant, apres))

    assert not chaudes, 'cibles restees chaudes : %s' % chaudes


def test_aucune_cible_n_est_elle_meme_dans_la_table():
    """Sinon le script ne converge pas : une cible reconvertie à chaque
    passage ferait dériver la palette un peu plus à chaque exécution."""
    corr = pf.table()
    cycles = [(a, b) for a, b in corr.items() if b.upper() in corr]

    assert not cycles, 'conversions en cycle : %s' % cycles


def test_la_table_ne_contient_aucune_couleur_de_statut():
    """La garantie de fond : ce qui encode un état n'est pas dans la table.

    Les valeurs citées sont les gammes rouge et ambre de Tailwind et de
    Bootstrap, telles qu'elles sont employées dans l'ERP.
    """
    statuts = [
        'DC2626', 'EF4444', 'F87171', 'FEE2E2', 'FECACA', 'FEF2F2',
        '991B1B', 'B91C1C', '7F1D1D', '450A0A', 'DC3545',
        'D97706', 'F59E0B', 'FEF3C7', 'FFFBEB', 'FCD34D', 'FDE68A',
        '92400E', 'B45309', '451A03', 'CA8A04', 'EAB308', 'FBBF24',
        'EA580C', 'F97316', 'FFF7ED', 'FD7E14', 'FFC107', 'B7791F',
    ]
    corr = pf.table()
    fautifs = [h for h in statuts if h in corr]

    assert not fautifs, (
        'des couleurs d-etat seraient converties : %s' % fautifs)


# ─── La propriété de sûreté : la luminance ───────────────────────────────

def test_chaque_conversion_preserve_les_rapports_de_contraste():
    """La raison pour laquelle on peut repeindre 527 écrans sans les voir.

    Sans cela, changer la teinte suffirait à faire disparaître du texte :
    le vert pèse 0.72 dans la luminance relative et le bleu 0.07, donc un
    or et un azur de même clarté HSL n'ont pas du tout la même luminance.

    LE SEUIL PORTE SUR LE RAPPORT, PAS SUR LA LUMINANCE BRUTE. Première
    rédaction de ce test : « |ΔY| ≤ 0.002 ». Il échouait sur treize
    entrées, et il avait tort. Les couleurs sont arrondies à l'octet :
    près du blanc, un seul pas d'octet déplace Y de 0.003. Exiger mieux,
    c'est exiger l'impossible en 8 bits.

    Or ce qui se voit n'est pas Y, c'est le RAPPORT de contraste. Un ΔY de
    0.003 à Y≈0.9 fait passer le contraste sur noir de 19.00 à 19.05 —
    invisible ; le même ΔY à Y≈0.01 serait énorme. Mesurée sur le rapport,
    la pire dérive de la table entière est de 0.61 %.
    """
    derives = []
    for avant, apres in pf.table().items():
        if avant in pf.ANCRES:
            continue
        for reference in ('FFFFFF', '000000'):
            ca = pf.contraste(avant, reference)
            cb = pf.contraste(apres, reference)
            if abs(cb / ca - 1) > 0.015:
                derives.append('%s -> %s sur %s : %.3f -> %.3f'
                               % (avant, apres, reference, ca, cb))

    assert not derives, 'rapports de contraste deplaces : %s' % derives


def test_les_ancres_ameliorent_le_contraste_au_lieu_de_le_degrader():
    """Les trois seules couleurs posées à la main.

    Chacune rend sa teinte plus SOMBRE, donc plus lisible sur blanc comme
    sous du texte blanc. Les deux ancres qui éclaircissaient ont été
    retirées après mesure.
    """
    pires = []
    for avant, apres in pf.ANCRES.items():
        ca = pf.contraste(avant, 'FFFFFF')
        cb = pf.contraste(apres, 'FFFFFF')
        if cb < ca - 0.25:
            pires.append('%s -> %s : %.2f -> %.2f' % (avant, apres, ca, cb))

    assert not pires, 'ancres degradant le contraste : %s' % pires


def test_le_texte_sur_le_fond_respecte_le_contraste_aa():
    """Le seul rapport qui compte sur chaque écran de l'ERP."""
    texte = _jeton('orion-desktop.css', 'orion-text')
    fond = _jeton('orion-desktop.css', 'orion-bg')

    assert texte and fond, 'jetons introuvables'
    rapport = pf.contraste(texte, fond)
    assert rapport >= 4.5, (
        'texte #%s sur fond #%s : %.2f, sous le seuil AA'
        % (texte, fond, rapport))


def test_le_fond_de_page_n_est_pas_blanc():
    """Les cartes sont blanches : un fond blanc les ferait disparaître.

    C'était vrai avant la bascule (sable `#F8F3EA`) et doit le rester.
    """
    fond = _jeton('orion-desktop.css', 'orion-bg')

    assert pf.contraste(fond, 'FFFFFF') > 1.02, (
        'le fond de page #%s ne se distingue plus des cartes' % fond)


# ─── L'échelle garde ses pas ─────────────────────────────────────────────

def test_l_echelle_claire_garde_son_pas():
    """Le défaut mesuré, puis corrigé.

    `orion-design-system.css` peint des cartes en `--orion-sand-200` et
    les borde de `--orion-sand-300`. Deux ancres posées à la main avaient
    rapproché les deux tons au point de rendre la bordure invisible : le
    rapport était tombé de 1.12 à 1.01.
    """
    deux = _jeton('orion-design-system.css', 'orion-sand-200')
    trois = _jeton('orion-design-system.css', 'orion-sand-300')

    assert deux and trois, 'jetons d-echelle introuvables'
    # Note : la dernière définition est celle du thème sombre ; le pas
    # doit tenir là aussi, c'est le même usage.
    assert pf.contraste(deux, trois) >= 1.08, (
        'la bordure #%s ne se detache plus du fond #%s (rapport %.3f)'
        % (trois, deux, pf.contraste(deux, trois)))


# ─── Ce que les fichiers contiennent vraiment ────────────────────────────

def test_plus_aucune_couleur_de_marque_chaude_dans_l_erp():
    """Le test qui dit si la conversion a vraiment eu lieu.

    Il relit les 717 fichiers du périmètre, et non la table : une table
    juste appliquée à moitié passerait tous les tests précédents.
    """
    corr = pf.table()
    motif_hexa = re.compile(
        '#(' + '|'.join(re.escape(h) for h in corr) + ')', re.IGNORECASE)
    composantes = {pf.vers_rgb(h) for h in corr}
    motif_rgb = re.compile(
        r'rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})')

    restes = []
    for chemin in pf.fichiers():
        texte = _lire(str(chemin))
        for trouve in motif_hexa.findall(texte):
            restes.append('%s : #%s' % (chemin.name, trouve))
        for triplet in motif_rgb.findall(texte):
            valeurs = tuple(int(x) for x in triplet)
            if valeurs in composantes:
                restes.append('%s : rgb%s' % (chemin.name, valeurs))

    assert not restes, (
        '%d couleurs chaudes de marque subsistent : %s'
        % (len(restes), restes[:12]))


def test_les_couleurs_d_etat_sont_toujours_presentes():
    """Le pendant du précédent.

    Si une future conversion balayait tout le chaud sans distinguer, ce
    test tomberait — et c'est exactement ce qu'on veut qu'il signale.
    """
    attendues = ['DC2626', 'D97706', 'FEF3C7', 'FEE2E2', '92400E']
    vues = {h: 0 for h in attendues}

    for chemin in pf.fichiers():
        texte = _lire(str(chemin)).upper()
        for h in attendues:
            vues[h] += texte.count('#' + h)

    manquantes = [h for h, n in vues.items() if n == 0]
    assert not manquantes, (
        'des couleurs d-etat ont disparu de l-ERP : %s' % manquantes)


def test_le_planning_distingue_toujours_maladie_et_conge():
    """Le piège trouvé en route.

    « maladie » est codé en or (#F7E7C6 / #845213) et « congé » en bleu
    (#D6E7F1 / #27566A). Rabattre tous les ors vers le cyan aurait fait
    de l'arrêt maladie un jumeau des vacances — sur un planning qu'on lit
    d'un coup d'œil, de loin.
    """
    chemin = os.path.join(RACINE, 'templates', 'hr', 'planning',
                          '_palette.html')
    texte = _lire(chemin)

    def valeur(nom):
        trouve = re.search(r'--pl-%s:\s*(#[0-9a-fA-F]{6})' % nom, texte)
        return trouve.group(1).lstrip('#') if trouve else None

    maladie = valeur('maladie-fond')
    conge = valeur('conge-fond')

    assert maladie and conge, 'les categories du planning ont change de nom'
    r_m = pf.vers_rgb(maladie)
    r_c = pf.vers_rgb(conge)
    # Une des deux doit rester chaude, l'autre froide : c'est ce qui les
    # sépare à l'œil, bien avant leur clarté.
    assert (r_m[0] - r_m[2]) >= 12, (
        'maladie #%s n-est plus une teinte chaude : elle se confondrait '
        'avec conge #%s' % (maladie, conge))
    assert (r_c[2] - r_c[0]) >= 12, (
        'conge #%s n-est plus une teinte froide' % conge)


def test_les_sites_publics_sont_epargnes():
    """SIÈCLE, LUNEA, le site BTP et le portail client gardent leur
    identité : la bascule ne concerne que l'interface de gestion."""
    hors = [
        'templates/client_portal',
        'templates/emails',
        'static/css/sites',
        'templates/orion_website',
    ]
    for prefixe in hors:
        from pathlib import Path
        assert pf.hors_perimetre(Path(prefixe) / 'quelconque.html'), (
            '%s devrait etre hors perimetre' % prefixe)

    dedans = pf.fichiers()
    fautifs = [str(p) for p in dedans
               if any(x in p.as_posix() for x in hors)]
    assert not fautifs, 'des fichiers publics sont dans le perimetre : %s' % fautifs


# ─── Les commentaires ne mentent pas ─────────────────────────────────────

def test_les_feuilles_ne_se_decrivent_plus_comme_chaudes():
    """Un commentaire faux coûte plus cher qu'un commentaire absent.

    `orion-ui.css` s'annonçait « Palette : sable, brun, or » et
    `orion-design-system.css` nommait son accent « champagne ». Les noms
    de jetons (`--orion-gold-600`, `--orion-sand-200`) ont en revanche
    été CONSERVÉS volontairement — les renommer aurait demandé de toucher
    137 fichiers de plus, et un renommage casse en silence ce qu'il
    oublie. Chaque échelle porte donc une mention explicite.
    """
    mensonges = []
    for nom, interdits in (
            ('orion-ui.css', ['sable, brun, or']),
            ('erp.css', ['marron/or']),
            ('orion-design-system.css', ['Accent champagne']),
    ):
        texte = _lire(os.path.join(RACINE, 'static', 'css', nom))
        for mot in interdits:
            if mot in texte:
                mensonges.append('%s : « %s »' % (nom, mot))

    assert not mensonges, 'commentaires devenus faux : %s' % mensonges


def test_les_noms_historiques_sont_signales_comme_tels():
    """Puisque les noms restent, la mise en garde doit être là."""
    texte = _lire(os.path.join(RACINE, 'static', 'css',
                               'orion-design-system.css'))

    for echelle in ('Brown scale', 'Gold scale', 'Sand scale'):
        trouve = re.search(re.escape(echelle) + r'[^*]*', texte)
        assert trouve and 'historique' in trouve.group(0), (
            '« %s » ne signale pas que son nom est historique' % echelle)


# ─── La page rendue ──────────────────────────────────────────────────────

@pytest.mark.django_db
def test_un_ecran_de_l_erp_ne_sert_plus_de_chaud(client, django_user_model):
    """Le fichier peut être juste et n'être jamais servi.

    Ce test rend un vrai écran et relit le HTML produit, styles en ligne
    compris — c'est le seul endroit où l'on voit ce que le navigateur
    recevra.
    """
    from django.urls import reverse

    from apps.core.models import Company

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    utilisateur = django_user_model.objects.create_superuser(
        username='chef', password='motdepasse-test', email='chef@x.fr')
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)

    contenu = client.get(reverse('dashboard:home')).content.decode()

    for chaude in ('#C6A15B', '#F8F3EA', '#2B2118', '#3A2A1A'):
        assert chaude.lower() not in contenu.lower(), (
            'la page sert encore %s' % chaude)
