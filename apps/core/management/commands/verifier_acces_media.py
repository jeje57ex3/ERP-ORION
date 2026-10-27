"""Confronte la politique de /media/ aux fichiers réellement présents.

Pourquoi cette commande existe : la politique de `media_access.py` refuse
par défaut, et c'est le bon défaut — mais il a un coût. Un `upload_to`
ajouté demain à un modèle tombera dans le refus **en silence**, et la
page qui affiche ces images montrera des cadres vides sans rien dire.

Cette commande transforme ce silence en liste. Elle lit les `upload_to`
déclarés par les modèles — pas une liste écrite à la main, qui aurait
vieilli — et les confronte à la politique, puis à ce qui est sur le
disque.

    manage.py verifier_acces_media
    manage.py verifier_acces_media --disque   (parcourt aussi MEDIA_ROOT)

Code de sortie 1 s'il existe un préfixe déclaré par un modèle et non
couvert par la politique : utilisable dans un contrôle de déploiement.
"""

import os
import sys

from django.core.management.base import BaseCommand
from django.db import models

from apps.core.media_access import (
    PREFIXES_AUTHENTIFIES,
    PREFIXES_INTERDITS,
    PREFIXES_PUBLICS,
    niveau_requis,
    raison_du_refus,
)


def prefixes_declares():
    """Les `upload_to` de tous les FileField et ImageField du projet.

    Lus sur les modèles chargés et non par un `grep` : une liste écrite à
    la main se périme, et c'est précisément le genre d'oubli que cette
    commande doit attraper.

    Les `upload_to` dynamiques (une fonction, pour un nom calculé) sont
    signalés à part : on ne peut pas en déduire un préfixe sans
    l'exécuter.
    """
    from django.apps import apps

    statiques, dynamiques = {}, []
    for modele in apps.get_models():
        for champ in modele._meta.get_fields():
            if not isinstance(champ, models.FileField):
                continue
            cible = getattr(champ, 'upload_to', '')
            etiquette = f'{modele._meta.label}.{champ.name}'
            if callable(cible):
                dynamiques.append(etiquette)
                continue
            if not cible:
                # Sans upload_to, le fichier atterrit à la racine de
                # MEDIA_ROOT, où la politique le refusera.
                dynamiques.append(f'{etiquette} (aucun upload_to)')
                continue
            chemin = str(cible).replace('\\', '/')
            # « documents/%Y/%m/ » : seule la partie fixe sert de préfixe.
            fixe = chemin.split('%')[0]
            statiques.setdefault(fixe, []).append(etiquette)
    return statiques, dynamiques


class Command(BaseCommand):
    help = ('Vérifie que chaque emplacement de fichiers téléversés est '
            'couvert par la politique de /media/.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--disque', action='store_true',
            help='Parcourt aussi MEDIA_ROOT pour compter les fichiers '
                 'réellement présents sous chaque préfixe.')

    def handle(self, *args, **options):
        from django.conf import settings

        self.stdout.write(self.style.MIGRATE_HEADING(
            'Politique de /media/ — refus par défaut'))
        self.stdout.write(
            f'  racine        : {settings.MEDIA_ROOT}\n'
            f'  publics       : {len(PREFIXES_PUBLICS)} préfixe(s)\n'
            f'  authentifiés  : {len(PREFIXES_AUTHENTIFIES)} préfixe(s)\n'
            f'  interdits     : {len(PREFIXES_INTERDITS)} préfixe(s) '
            f'documentés\n')

        statiques, dynamiques = prefixes_declares()

        par_niveau = {'public': [], 'authentifie': [], 'interdit': []}
        for prefixe in sorted(statiques):
            par_niveau[niveau_requis(prefixe)].append(prefixe)

        self.stdout.write(self.style.MIGRATE_HEADING(
            'Servis aux visiteurs anonymes'))
        for prefixe in par_niveau['public']:
            self.stdout.write(f'  + {prefixe}')

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            'Servis aux utilisateurs connectés'))
        for prefixe in par_niveau['authentifie']:
            self.stdout.write(f'  + {prefixe}')

        # Les refusés : on distingue « refusé à dessein » de « oublié ».
        # C'est toute la valeur de la commande.
        voulus, oublies = [], []
        for prefixe in par_niveau['interdit']:
            if any(prefixe.startswith(p) or p.startswith(prefixe)
                   for p in PREFIXES_INTERDITS):
                voulus.append(prefixe)
            else:
                oublies.append(prefixe)

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            'Refusés à dessein — accessibles par leurs vues dédiées'))
        for prefixe in voulus:
            self.stdout.write(f'  - {prefixe}')
            self.stdout.write(f'      {raison_du_refus(prefixe)}')

        if dynamiques:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                'Noms de fichiers calculés — préfixe indéterminable :'))
            for etiquette in dynamiques:
                self.stdout.write(f'  ? {etiquette}')

        if options['disque']:
            self._parcourir_le_disque(settings.MEDIA_ROOT)

        self.stdout.write('')
        if oublies:
            self.stdout.write(self.style.ERROR(
                f'{len(oublies)} préfixe(s) déclaré(s) par un modèle et '
                f'NON couvert(s) par la politique. Ces fichiers ne seront '
                f'pas servis, et la page qui les affiche montrera des '
                f'cadres vides sans message d\'erreur :'))
            for prefixe in oublies:
                champs = ', '.join(statiques[prefixe])
                self.stdout.write(f'  ! {prefixe}')
                self.stdout.write(f'      {champs}')
            self.stdout.write(
                '\nPour chacun : décidez s\'il doit être public, réservé '
                'aux comptes connectés, ou servi par une vue qui contrôle '
                'les droits — puis complétez la liste correspondante dans '
                'apps/core/media_access.py.')
            # sys.exit et non « return 1 » : Django ECRIT la valeur rendue
            # par handle() sur la sortie standard, et 1 n'est pas une
            # chaine -- la commande mourait sur un AttributeError au lieu
            # de signaler proprement son echec.
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS(
            'Tous les emplacements déclarés par les modèles sont couverts '
            'par la politique.'))

    def _parcourir_le_disque(self, racine):
        """Ce qui est réellement là, regroupé par préfixe de premier niveau.

        Utile après une migration de disque : un préfixe présent sur le
        disque mais absent des modèles est un reste d'une version
        precedente, et il occupe de la place pour rien.
        """
        racine = str(racine)
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Fichiers présents sous {racine}'))
        if not os.path.isdir(racine):
            self.stdout.write('  (le dossier n\'existe pas)')
            return

        totaux = {}
        for dossier, _sous, fichiers in os.walk(racine, followlinks=False):
            relatif = os.path.relpath(dossier, racine).replace('\\', '/')
            tete = relatif.split('/')[0] if relatif != '.' else '(racine)'
            entree = totaux.setdefault(tete, {'nombre': 0, 'octets': 0})
            for nom in fichiers:
                try:
                    entree['octets'] += os.lstat(
                        os.path.join(dossier, nom)).st_size
                except OSError:
                    continue
                entree['nombre'] += 1

        for tete in sorted(totaux, key=lambda t: -totaux[t]['octets']):
            info = totaux[tete]
            if not info['nombre']:
                continue
            niveau = niveau_requis(tete + '/')
            marque = {'public': '+', 'authentifie': '+',
                      'interdit': '-'}[niveau]
            self.stdout.write(
                f'  {marque} {tete:<28} {info["nombre"]:>6} fichier(s)  '
                f'{info["octets"] / 1048576:>9.1f} Mo  [{niveau}]')
