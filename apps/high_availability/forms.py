from django import forms
from apps.high_availability.models import OrionHASettings, OrionHANode


class OrionHASettingsForm(forms.ModelForm):
    class Meta:
        model = OrionHASettings
        fields = [
            'failover_enabled',
            'automatic_failover_enabled',
            'require_manual_confirmation',
            'failover_after_seconds',
            'max_allowed_replication_lag_seconds',
            'minimum_healthy_secondaries',
            'preferred_secondary_node',
            'allow_failover_to_secondary_2',
            'failback_policy',
            'failback_min_stable_seconds',
            'media_sync_enabled',
            'database_replication_check_enabled',
            'cloudflare_failover_enabled',
            'cloudflare_zone_id',
            'cloudflare_dns_record_id',
            'cloudflare_record_name',
            'notify_admins',
            'notify_email',
            'split_brain_protection_enabled',
            'maintenance_mode_enabled',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_secondary_node'].queryset = OrionHANode.objects.filter(
            role='secondary',
            is_enabled=True,
        ).order_by('priority')

    def clean(self):
        cleaned_data = super().clean()
        automatic = cleaned_data.get('automatic_failover_enabled')
        manual_confirmation = cleaned_data.get('require_manual_confirmation')
        failover_after = cleaned_data.get('failover_after_seconds')
        max_lag = cleaned_data.get('max_allowed_replication_lag_seconds')

        if automatic and manual_confirmation:
            raise forms.ValidationError(
                'Le failover automatique ne peut pas être activé si la confirmation manuelle est obligatoire.'
            )
        if failover_after and failover_after < 60:
            raise forms.ValidationError(
                'Le délai de failover doit être au minimum de 60 secondes.'
            )
        if max_lag is not None and max_lag > 300:
            raise forms.ValidationError(
                'Le retard de réplication maximum ne doit pas dépasser 300 secondes.'
            )
        return cleaned_data


class OrionHANodeForm(forms.ModelForm):
    class Meta:
        model = OrionHANode
        fields = [
            'node_id',
            'name',
            'role',
            'status',
            'base_url',
            'public_ip',
            'private_ip',
            'region',
            'priority',
            'is_enabled',
            'is_current_active',
            'is_failover_target',
            'allow_auto_failover',
            'notes',
        ]

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        is_current_active = cleaned_data.get('is_current_active')

        # Le rang de préséance n'est PLUS lié au rôle. Les deux règles qui les
        # couplaient ici rendaient inéditable tout serveur ayant connu une
        # bascule : le promu portait le rôle principal avec un rang 2, et
        # l'ancien principal rétrogradé gardait son rang 1 — chacun des deux
        # cas déclenchait une erreur de validation sur une situation
        # parfaitement normale.
        if is_current_active and role != 'primary':
            raise forms.ValidationError(
                'Le serveur actif doit porter le rôle principal.'
            )

        if is_current_active:
            qs = OrionHANode.objects.filter(is_current_active=True)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Un autre serveur est déjà marqué comme actif.')

        return cleaned_data


class OrionHAConnectForm(forms.Form):
    """Raccordement d'un serveur au cluster : le strict nécessaire.

    L'identifiant du nœud n'y figure pas, volontairement. Il est relevé sur le
    serveur distant, seule source qui ne puisse pas se désynchroniser de son
    ORION_NODE_ID — et un identifiant saisi à la main qui en diffère donne un
    serveur qui refuse toutes les écritures sans que rien ne l'explique.
    """

    base_url = forms.CharField(
        label='Adresse du serveur',
        max_length=200,
        help_text='Son sous-domaine propre, par exemple serveur2.exemple.fr. '
                  'Le https:// est ajouté si vous l\'omettez.',
    )
    name = forms.CharField(label='Nom affiché', max_length=180)
    priority = forms.IntegerField(
        label='Rang de préséance',
        min_value=1,
        help_text='1 reprend la main en priorité. Indépendant du rôle courant.',
    )
    region = forms.CharField(label='Emplacement', max_length=80, required=False)
    is_failover_target = forms.BooleanField(
        label='Peut recevoir la main', required=False, initial=True,
    )
    allow_auto_failover = forms.BooleanField(
        label='Promotion automatique autorisée', required=False, initial=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # La feuille de style ne cible nommément que text/email/tel : un champ
        # entier, rendu en <input type="number">, resterait sans habillage.
        for champ in self.fields.values():
            if not isinstance(champ.widget, forms.CheckboxInput):
                champ.widget.attrs.setdefault('class', 'orion-form-control')


class OrionHAClusterForm(forms.ModelForm):
    """Réglages de la grappe : un domaine, un motif, et c'est tout.

    Le rang et l'adresse de chaque serveur se déduisent du nommage, au lieu
    d'être saisis séparément pour chaque machine — deux données qui pouvaient
    se contredire.
    """

    class Meta:
        model = OrionHASettings
        fields = [
            'cluster_base_domain',
            'node_name_pattern',
            'cluster_max_nodes',
            'cluster_use_https',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            if not isinstance(champ.widget, forms.CheckboxInput):
                champ.widget.attrs.setdefault('class', 'orion-form-control')

    def clean_node_name_pattern(self):
        motif = (self.cleaned_data.get('node_name_pattern') or '').strip()
        if '{n}' not in motif:
            raise forms.ValidationError(
                'Le motif doit contenir {n}, remplacé par le rang du serveur '
                '(ex. serveur{n}).'
            )
        if '.' in motif:
            raise forms.ValidationError(
                'Le motif ne porte que le préfixe, sans point : le domaine de '
                'la grappe est ajouté automatiquement.'
            )
        return motif

    def clean_cluster_base_domain(self):
        base = (self.cleaned_data.get('cluster_base_domain') or '').strip()
        base = base.strip('.').lower()
        if base.startswith('http://') or base.startswith('https://'):
            raise forms.ValidationError(
                "Indiquez le domaine seul, sans https:// — le schéma est "
                'choisi par la case ci-dessous.'
            )
        if base and '.' not in base:
            raise forms.ValidationError(
                'Domaine incomplet : il faut un nom de domaine entier '
                '(ex. exemple.fr).'
            )
        return base


class OrionHAMeshForm(forms.ModelForm):
    """Réglages du réseau privé : un sous-réseau, un port.

    Ces deux champs existaient sur le modèle sans être exposés nulle part :
    impossible de les changer autrement qu'en base. Le reste de la
    configuration WireGuard se déduit du rang du serveur.
    """

    class Meta:
        model = OrionHASettings
        fields = ['mesh_subnet', 'mesh_port']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs.setdefault('class', 'orion-form-control')

    def clean_mesh_subnet(self):
        import ipaddress

        brut = (self.cleaned_data.get('mesh_subnet') or '').strip()
        try:
            reseau = ipaddress.ip_network(brut, strict=False)
        except ValueError:
            raise forms.ValidationError(
                'Sous-réseau illisible. Attendu : une notation CIDR comme '
                '10.10.0.0/24.'
            )
        if not reseau.is_private:
            raise forms.ValidationError(
                'Utilisez une plage privée (10.x, 172.16-31.x, 192.168.x) : '
                'une plage publique détournerait du trafic qui ne vous '
                'appartient pas.'
            )
        if reseau.num_addresses < 4:
            raise forms.ValidationError(
                f'{reseau} ne laisse aucune place pour des serveurs. '
                'Élargissez le préfixe.'
            )
        return str(reseau)

    def clean_mesh_port(self):
        port = self.cleaned_data.get('mesh_port') or 0
        if not (1024 <= port <= 65535):
            raise forms.ValidationError(
                'Choisissez un port entre 1024 et 65535.'
            )
        return port


class OrionHAPeerForm(forms.Form):
    """Déclaration d'un pair WireGuard.

    L'adresse privée n'est pas demandée : elle se déduit du rang. Demander les
    deux permettrait de les saisir en désaccord.
    """

    rang = forms.IntegerField(
        label='Rang du serveur', min_value=1,
        help_text='Son rang dans la grappe : 2 pour serveur2, 3 pour serveur3…',
    )
    cle_publique = forms.CharField(
        label='Clé publique WireGuard',
        help_text="Affichée par « Initialiser » sur l'autre serveur.",
    )
    endpoint = forms.CharField(
        label='Adresse publique et port', required=False,
        help_text='Ex. serveur2.exemple.fr:51820. Facultatif si ce serveur-ci '
                  'est derrière un NAT et que l\'autre initie la liaison.',
    )

    def __init__(self, *args, rang_local=None, cle_locale='', **kwargs):
        self.rang_local = str(rang_local or '')
        self.cle_locale = (cle_locale or '').strip()
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs.setdefault('class', 'orion-form-control')

    def clean_rang(self):
        rang = self.cleaned_data.get('rang')
        if self.rang_local and str(rang) == self.rang_local:
            raise forms.ValidationError(
                f'Le rang {rang} est celui de CE serveur. Indiquez le rang de '
                "l'AUTRE serveur."
            )
        return rang

    def clean_cle_publique(self):
        cle = (self.cleaned_data.get('cle_publique') or '').strip()
        if self.cle_locale and cle == self.cle_locale:
            raise forms.ValidationError(
                'Cette clé est celle de CE serveur. WireGuard refuse un pair '
                "portant la clé de l'interface, et l'interface resterait "
                "arrêtée. Copiez la clé affichée sur l'AUTRE serveur."
            )
        # Une clé WireGuard est 32 octets en base64, soit 44 caractères finissant
        # par « = ». Le contrôle évite d'écrire dans la configuration une ligne
        # que wg-quick refusera ensuite, en laissant l'interface inactive.
        if len(cle) != 44 or not cle.endswith('='):
            raise forms.ValidationError(
                'Une clé publique WireGuard fait 44 caractères et se termine '
                "par « = ». Vérifiez que vous n'avez pas collé autre chose, "
                "comme une clé SSH ou la sortie complète d'une commande."
            )
        return cle
