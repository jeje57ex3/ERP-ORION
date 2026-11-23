"""Le stockage des messages flash, qui les traduit à l'affichage.

**POURQUOI ICI ET NON DANS LES GABARITS.** Un filtre de gabarit aurait
demandé de retoucher chaque endroit qui rend `{% for message in messages %}`
— il y en a des dizaines, et le premier oublié afficherait du français au
milieu du portugais sans que rien ne le dise. C'est le défaut que ce dépôt
rencontre à chaque audit : une moitié livrée sans l'autre n'erre pas, elle
efface.

Le stockage est le seul point par lequel **tous** les messages passent, quel
que soit le gabarit qui les affiche.

**POURQUOI À LA LECTURE ET NON À L'ÉCRITURE.** Un message flash est écrit
pendant une requête et lu pendant la SUIVANTE, après une redirection. Le
traduire à l'écriture figerait la langue active au moment du POST ; à la
lecture, c'est la langue de la page qui l'affiche qui décide — et c'est
elle que l'utilisateur a sous les yeux.

**ON DÉRIVE DE `SessionStorage`, ET IL FALLAIT LE VÉRIFIER.** Le défaut de
Django est `FallbackStorage` (session, puis cookie en secours), mais ce
projet déclare explicitement
`MESSAGE_STORAGE = '…storage.session.SessionStorage'` dans `base.py`. En
dériver de `FallbackStorage` aurait **changé le stockage au passage** :
les messages se seraient mis à repartir en cookie quand la session est
pleine, c'est-à-dire à traverser le réseau en clair alors que ce projet a
choisi de les garder côté serveur.

Ajouter une traduction ne doit rien changer d'autre. Un changement mêlé à
un autre fait chercher la panne au mauvais endroit.
"""

from django.contrib.messages.storage.session import SessionStorage

from apps.translations.messages_auto import traduire


class StockageTraduit(SessionStorage):
    """`SessionStorage`, dont les messages sortent dans la langue active."""

    def _get(self, *args, **kwargs):
        """Lit les messages, puis les traduit un par un.

        `_get` rend `(messages, tout_recupere)`, et `messages` peut valoir
        None quand rien n'est stocké — le tester est nécessaire, une
        itération sur None faisant tomber toutes les pages du site.

        LE TEXTE D'ORIGINE EST REMPLACÉ EN PLACE sur l'objet `Message`
        plutôt que par une nouvelle liste d'objets : `Message` porte aussi
        un niveau et des étiquettes CSS, et le reconstruire en oublierait
        un jour une — le bandeau perdrait sa couleur, et on chercherait du
        côté du CSS.
        """
        messages, tout_recupere = super()._get(*args, **kwargs)
        if not messages:
            return messages, tout_recupere

        for message in messages:
            try:
                message.message = traduire(message.message)
            except Exception:
                # Un message dans la mauvaise langue vaut mieux qu'une page
                # qui ne s'affiche pas. On garde le texte d'origine.
                continue
        return messages, tout_recupere
