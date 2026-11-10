# -*- coding: utf-8 -*-
"""La barre latérale en pastille bleue, et ce qui la rend sûre.

Neuf feuilles de style décrivent déjà cette barre, et cinq d'entre elles
lisent le même jeton `--orion-menu-bg`. Poser la refonte dans l'une
d'elles, c'est risquer qu'une autre la réécrive selon l'ordre de
chargement — et personne ne saurait laquelle gagne sans les lire toutes.

D'où une feuille à part, chargée EN DERNIER. Ces tests tiennent les trois
propriétés dont dépend ce choix :

1. elle est bien la dernière, sans quoi elle ne gagne pas ;
2. elle redéfinit le jeton que les autres lisent, plutôt que de les
   contredire une par une ;
3. la refonte tient en UNE ligne de base.html, et la retirer suffit à
   rendre la barre à sa couleur de fond habituelle.

   Une précision est devenue nécessaire : à la création de cette feuille,
   retirer cette ligne rendait à l'ERP son aspect brun d'origine. Depuis
   la bascule de la palette vers l'ardoise et l'azur
   (`scripts/palette_froide.py`), ce n'est plus vrai : la retirer donne
   une barre ardoise sur une interface froide. Cohérent, mais pas un
   retour en arrière. Le retour en arrière complet, c'est `git revert`
   des deux lots.

Et un quatrième, qui n'est pas technique : **la navigation n'a pas été
sacrifiée à l'esthétique**. L'ERP porte 29 modules et une centaine de
sous-entrées ; les réduire à des icônes sans nom l'aurait rendu
illisible. Un test l'interdit, parce que c'est exactement la pente d'une
prochaine « simplification ».
"""

import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(RACINE, 'templates', 'base.html')
ERP_BASE = os.path.join(RACINE, 'templates', 'erp_base.html')
FEUILLE = os.path.join(RACINE, 'static', 'css', 'orion-barre-bleue.css')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


# ─── L'invariant de chargement ────────────────────────────────────────────

def test_la_feuille_existe():
    assert os.path.isfile(FEUILLE)


def test_elle_est_chargee_en_dernier():
    """Si une autre feuille la suit, la refonte est écrasée en silence.

    C'est la seule chose qui fait qu'elle gagne : elle ne surenchérit sur
    aucune spécificité, elle arrive après.
    """
    feuilles = re.findall(r"\{% static 'css/([^']+)' %\}", _lire(BASE))

    assert feuilles, 'aucune feuille trouvee dans base.html'
    assert feuilles[-1] == 'orion-barre-bleue.css', (
        'la refonte doit etre la DERNIERE feuille chargee ; actuellement '
        'la derniere est %s' % feuilles[-1])


def test_elle_redefinit_le_jeton_que_les_autres_lisent():
    """Cinq feuilles lisent `--orion-menu-bg` : le redéfinir les atteint
    toutes, sans en modifier aucune."""
    assert '--orion-menu-bg' in _lire(FEUILLE)


def test_le_jeton_est_bien_partage_par_les_autres_feuilles():
    """Le test qui justifie le précédent.

    S'il échouait, c'est que les feuilles auraient cessé de lire ce jeton,
    et la refonte ne les atteindrait plus — sans que rien ne le signale.
    """
    dossier = os.path.join(RACINE, 'static', 'css')
    lectrices = [nom for nom in os.listdir(dossier)
                 if nom.endswith('.css') and nom != 'orion-barre-bleue.css'
                 and 'var(--orion-menu-bg' in _lire(
                     os.path.join(dossier, nom))]

    assert len(lectrices) >= 3, (
        'le jeton n-est plus partage : %s' % lectrices)


def test_le_retour_en_arriere_tient_en_une_ligne():
    """Sur un changement qui touche chaque écran, pouvoir revenir vite
    vaut mieux que la confiance."""
    base = _lire(BASE)
    lignes = [l for l in base.splitlines() if 'orion-barre-bleue.css' in l]

    assert len(lignes) == 1, (
        'la refonte doit tenir en une seule ligne de base.html')


# ─── La navigation n'est pas sacrifiée ────────────────────────────────────

def test_les_libelles_des_modules_restent_affiches():
    """29 modules et ~100 sous-entrées : des icônes sans nom les perdraient.

    Ce test existe parce que c'est la pente naturelle d'une prochaine
    refonte « épurée », et que personne ne s'apercevrait de la perte avant
    de chercher une page qu'on ne trouve plus.
    """
    erp = _lire(ERP_BASE)

    assert 'nav-label' in erp, 'les libelles de modules ont disparu'
    assert 'nav-submenu' in erp, 'les sous-entrees ont disparu'
    assert 'nav-sublink' in erp


def test_la_largeur_reservee_au_contenu_ne_change_pas():
    """La pastille flotte DANS la largeur existante.

    Si `--sidebar-width` changeait, chaque écran de l'ERP aurait besoin
    d'un décalage différent, et on le découvrirait page par page.
    """
    feuille = _lire(FEUILLE)

    assert '--sidebar-width:' not in feuille, (
        'la refonte redefinit la largeur reservee : tout le contenu de '
        'l-ERP se decalerait')
    assert 'calc(var(--sidebar-width)' in feuille, (
        'la pastille doit se caler SUR la largeur existante')


# ─── Ce que la feuille promet ─────────────────────────────────────────────

def test_la_barre_est_une_pastille_flottante():
    feuille = _lire(FEUILLE)

    assert 'border-radius' in feuille
    assert 'box-shadow' in feuille, 'la lueur de la maquette manque'


def test_les_accents_de_l_erp_suivent_la_barre():
    """« Barre + accents » : une barre bleue sur une interface dorée se
    verrait comme une pièce rapportée."""
    feuille = _lire(FEUILLE)

    assert '--orion-primary:' in feuille
    assert '.btn-primary' in feuille, (
        'les boutons qui codent leur couleur en dur ne suivraient pas')


def test_le_cas_mobile_est_traite():
    """En dessous de 992 px la barre glisse par-dessus le contenu : une
    pastille décollée y laisserait des bandes de fond de part et
    d'autre."""
    feuille = _lire(FEUILLE)

    assert '@media (max-width: 991.98px)' in feuille


def test_la_feuille_ne_reference_aucun_fichier():
    """`CompressedManifestStaticFilesStorage` fait échouer collectstatic
    sur une URL introuvable — et collectstatic tourne à chaque mise à jour.

    Une image ou une police citée ici et absente casserait donc le
    déploiement entier, loin de sa cause.
    """
    assert 'url(' not in _lire(FEUILLE)


# ─── Ce que la page rend vraiment ─────────────────────────────────────────

@pytest.mark.django_db
def test_la_page_charge_bien_la_feuille(client, django_user_model):
    """Le fichier peut exister et n'être jamais servi — c'est arrivé deux
    fois cette semaine, sur un middleware et sur un assistant."""
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

    assert 'orion-barre-bleue.css' in contenu
