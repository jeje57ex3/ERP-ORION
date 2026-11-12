"""« Mise à jour échouée : your local changes would be overwritten by merge. »

LA PANNE QUE CHAQUE MISE À JOUR POSAIT POUR LA SUIVANTE

Deux dossiers sont des SORTIES DE BUILD et sont pourtant suivis par git :
« static/siecle-store » et « apps/lunea/static/lunea/dist ». On les versionne
parce que l'appliance n'a pas toujours de quoi compiler.

Seulement, la mise à jour reconstruit les deux frontends juste APRÈS avoir
tiré le code. Chaque mise à jour réussie laissait donc ces fichiers modifiés
dans la copie de travail, et le « git pull » de la SUIVANTE refusait de
s'exécuter.

Le défaut ne pouvait pas se voir sur une mise à jour isolée : il fallait deux
mises à jour de suite, dont une touchant la boutique. C'est pourquoi il a
dormi jusqu'au jour où la boutique SIÈCLE a changé d'habillage.

POURQUOI CE TEST MONTE UN VRAI DÉPÔT

Simuler git par un mock prouverait seulement que le mock répond ce qu'on lui
a soufflé. Ici on monte deux dépôts réels, on REPRODUIT l'échec du pull, puis
on montre que la restauration le débloque. Sans la reproduction préalable, un
test qui passe ne dirait pas s'il protège de quoi que ce soit.
"""
import subprocess

import pytest

from apps.system_updates.git_service import (CHEMINS_GENERES, _est_genere,
                                             fichiers_modifies,
                                             restaurer_les_fichiers_generes)


GENERE = 'static/siecle-store/index.html'
A_MOI = 'apps/crm/views.py'


def git(*args, cwd):
    return subprocess.run(['git', *args], cwd=str(cwd), capture_output=True,
                          text=True)


def ecrire(racine, chemin, contenu):
    cible = racine / chemin
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(contenu, encoding='utf-8')


@pytest.fixture
def depots(tmp_path):
    """Un dépôt « amont » et une copie de travail, comme sur la VM."""
    amont = tmp_path / 'amont'
    amont.mkdir()
    git('init', '--bare', '-b', 'main', cwd=amont)

    travail = tmp_path / 'travail'
    travail.mkdir()
    git('init', '-b', 'main', cwd=travail)
    git('config', 'user.email', 'test@local', cwd=travail)
    git('config', 'user.name', 'Test', cwd=travail)

    ecrire(travail, GENERE, '<html>version 1</html>')
    ecrire(travail, A_MOI, '# mon travail en cours\n')
    git('add', '-A', cwd=travail)
    git('commit', '-m', 'depart', cwd=travail)
    git('remote', 'add', 'origin', str(amont), cwd=travail)
    git('push', 'origin', 'main', cwd=travail)

    # Une mise à jour arrive en amont, et elle TOUCHE le fichier généré :
    # c'est le cas réel, la boutique ayant changé d'habillage.
    autre = tmp_path / 'autre'
    git('clone', str(amont), str(autre), cwd=tmp_path)
    git('config', 'user.email', 'test@local', cwd=autre)
    git('config', 'user.name', 'Test', cwd=autre)
    ecrire(autre, GENERE, '<html>version 2</html>')
    git('add', '-A', cwd=autre)
    git('commit', '-m', 'nouvelle boutique', cwd=autre)
    git('push', 'origin', 'main', cwd=autre)

    return travail


def test_les_chemins_generes_sont_ceux_des_deux_frontends():
    """Si un frontend change de dossier de sortie sans être ajouté ici, la
    panne revient — en silence, et seulement une mise à jour plus tard."""
    assert 'static/siecle-store' in CHEMINS_GENERES
    assert 'apps/lunea/static/lunea/dist' in CHEMINS_GENERES


def test_un_fichier_hors_build_n_est_jamais_pris_pour_un_genere():
    assert _est_genere('static/siecle-store/index.html') is True
    assert _est_genere('static/siecle-store') is True
    assert _est_genere('apps/lunea/static/lunea/dist/app.js') is True
    # Le piège du préfixe : ce dossier commence par les mêmes lettres sans
    # être le même. Une comparaison par « startswith » nue l'écraserait.
    assert _est_genere('static/siecle-store-sauvegarde/x.js') is False
    assert _est_genere('apps/crm/views.py') is False


def test_la_panne_se_reproduit_sans_la_restauration(depots):
    """D'ABORD MONTRER L'ÉCHEC, sinon le test suivant ne prouve rien."""
    ecrire(depots, GENERE, '<html>sortie du build local</html>')

    tire = git('pull', 'origin', 'main', cwd=depots)

    assert tire.returncode != 0, 'le pull aurait dû échouer'
    sortie = (tire.stdout + tire.stderr).lower()
    assert 'would be overwritten' in sortie
    assert 'siecle-store' in sortie


def test_la_restauration_debloque_la_mise_a_jour(depots):
    """LA GARANTIE CENTRALE : le même scénario passe après restauration."""
    ecrire(depots, GENERE, '<html>sortie du build local</html>')

    restaures, autres = restaurer_les_fichiers_generes(depots)

    assert GENERE in restaures
    assert autres == []

    tire = git('pull', 'origin', 'main', cwd=depots)
    assert tire.returncode == 0, tire.stdout + tire.stderr
    assert (depots / GENERE).read_text(encoding='utf-8') == '<html>version 2</html>'


def test_le_travail_en_cours_de_l_exploitant_n_est_pas_touche(depots):
    """CE QU'ON NE FAIT PAS, ET POURQUOI.

    Un « git reset --hard » débloquerait aussi le pull — en effaçant au
    passage les fichiers que quelqu'un est en train de modifier sur la
    machine. On ne restaure que ce qu'on sait regénérer.
    """
    ecrire(depots, GENERE, '<html>sortie du build local</html>')
    ecrire(depots, A_MOI, '# une correction que je viens d’ecrire\n')

    restaures, autres = restaurer_les_fichiers_generes(depots)

    assert restaures == [GENERE]
    assert autres == [A_MOI], 'le fichier hors build doit être signalé'
    assert 'correction' in (depots / A_MOI).read_text(encoding='utf-8'), (
        'le travail en cours a été écrasé')


def test_les_bundles_non_suivis_sont_balayes(depots):
    """Un build laisse des bundles aux noms hachés, non suivis. Ils
    s'accumulent, et un fichier entrant du même nom ferait échouer le pull à
    son tour — « untracked working tree files would be overwritten »."""
    ecrire(depots, GENERE, '<html>sortie du build local</html>')
    ecrire(depots, 'static/siecle-store/assets/vieux-A1B2C3.js', 'xx')

    restaurer_les_fichiers_generes(depots)

    assert not (depots / 'static/siecle-store/assets/vieux-A1B2C3.js').exists()


def test_sans_rien_de_modifie_la_restauration_ne_fait_rien(depots):
    """Le cas courant : une mise à jour sur une copie propre."""
    assert fichiers_modifies(depots) == []
    assert restaurer_les_fichiers_generes(depots) == ([], [])
