"""
apps/dashboard/views.py — Vues du dashboard personnalisable Orion ERP
"""
import json
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView

from .models import DashboardWidget, UserDashboardWidget, DashboardShortcut, DashboardProfile
from .forms import DashboardShortcutForm, UserDashboardWidgetConfigForm, DashboardPreferenceForm, DashboardLayoutForm
from .services import (
    get_or_create_default_dashboard, get_available_widgets, get_user_widgets,
    get_user_shortcuts, get_dashboard_context, reset_user_dashboard,
    get_user_preference, user_can_add_widget,
)


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_staff:
            from django.shortcuts import redirect as _redirect
            return _redirect('client_portal:dashboard')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        company = getattr(self.request, 'current_company', None)
        if company is None:
            ctx['page_title'] = 'Mon tableau de bord'
            return ctx
        ctx.update(get_dashboard_context(user, company))
        ctx['page_title'] = 'Mon tableau de bord'
        ctx['page_subtitle'] = 'Personnalisez votre espace de travail avec vos raccourcis, demandes, tâches et indicateurs.'
        return ctx


class DashboardCustomizeView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/customize.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        company = self.request.current_company
        profile = get_or_create_default_dashboard(user, company)
        user_widget_codes = set(profile.user_widgets.values_list('widget__code', flat=True))
        available = get_available_widgets(user, company)
        ctx.update({
            'page_title': 'Personnaliser mon dashboard',
            'page_subtitle': 'Choisissez les widgets, raccourcis et informations à afficher.',
            'dashboard_profile': profile,
            'user_widgets': get_user_widgets(user, company, profile),
            'available_widgets': available,
            'user_widget_codes': user_widget_codes,
            'user_shortcuts': get_user_shortcuts(user, company),
            'shortcut_form': DashboardShortcutForm(),
            'pref_form': DashboardPreferenceForm(instance=get_user_preference(user, company)),
            'layout_form': DashboardLayoutForm(instance=profile),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        user = request.user
        company = request.current_company
        profile = get_or_create_default_dashboard(user, company)
        action = request.POST.get('action')

        if action == 'save_preferences':
            pref = get_user_preference(user, company)
            form = DashboardPreferenceForm(request.POST, instance=pref)
            if form.is_valid():
                form.save()
                messages.success(request, 'Vos préférences ont été enregistrées.')
            return redirect('dashboard:customize')

        if action == 'save_layout':
            form = DashboardLayoutForm(request.POST, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, 'La disposition a été enregistrée.')
            return redirect('dashboard:customize')

        return redirect('dashboard:customize')


class WidgetCatalogView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/widget_catalog.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        company = self.request.current_company
        profile = get_or_create_default_dashboard(user, company)
        user_widget_codes = set(profile.user_widgets.values_list('widget__code', flat=True))
        from .models import DashboardWidget
        ctx.update({
            'page_title': 'Catalogue de widgets',
            'available_widgets': get_available_widgets(user, company),
            'user_widget_codes': user_widget_codes,
            'widget_types': DashboardWidget.WIDGET_TYPES,
        })
        return ctx


class AddWidgetView(LoginRequiredMixin, View):
    def post(self, request, widget_id):
        user = request.user
        company = request.current_company
        widget = get_object_or_404(DashboardWidget, pk=widget_id, is_active=True)

        if not user_can_add_widget(user, company, widget):
            messages.error(request, "Vous n'avez pas accès à ce widget.")
            return redirect('dashboard:widget_catalog')

        profile = get_or_create_default_dashboard(user, company)
        max_y = profile.user_widgets.order_by('-position_y').values_list('position_y', flat=True).first() or 0
        _, created = UserDashboardWidget.objects.get_or_create(
            dashboard_profile=profile,
            widget=widget,
            defaults={
                'position_x': 0,
                'position_y': max_y + 1,
                'width': widget.default_width,
                'height': widget.default_height,
                'is_visible': True,
            }
        )
        if created:
            messages.success(request, f'Le widget « {widget.name} » a été ajouté.')
        else:
            messages.info(request, f'Le widget « {widget.name} » est déjà sur votre dashboard.')
        return redirect(request.POST.get('next', 'dashboard:home'))


class ConfigureWidgetView(LoginRequiredMixin, View):
    def get(self, request, pk):
        uw = get_object_or_404(UserDashboardWidget, pk=pk, dashboard_profile__user=request.user)
        form = UserDashboardWidgetConfigForm(instance=uw)
        return TemplateView.as_view(
            template_name='dashboard/widget_configure.html',
            extra_context={'form': form, 'user_widget': uw, 'page_title': f'Configurer — {uw.get_display_title()}'}
        )(request)

    def post(self, request, pk):
        uw = get_object_or_404(UserDashboardWidget, pk=pk, dashboard_profile__user=request.user)
        form = UserDashboardWidgetConfigForm(request.POST, instance=uw)
        if form.is_valid():
            form.save()
            messages.success(request, 'Le widget a été mis à jour.')
        return redirect('dashboard:home')


class RemoveWidgetView(LoginRequiredMixin, View):
    def post(self, request, pk):
        uw = get_object_or_404(UserDashboardWidget, pk=pk, dashboard_profile__user=request.user)
        name = uw.get_display_title()
        uw.delete()
        messages.success(request, f'Le widget « {name} » a été supprimé.')
        return redirect(request.POST.get('next', 'dashboard:home'))


class ToggleWidgetView(LoginRequiredMixin, View):
    def post(self, request, pk):
        uw = get_object_or_404(UserDashboardWidget, pk=pk, dashboard_profile__user=request.user)
        uw.is_visible = not uw.is_visible
        uw.save(update_fields=['is_visible'])
        if uw.is_visible:
            messages.success(request, f'Le widget « {uw.get_display_title()} » est maintenant visible.')
        else:
            messages.info(request, f'Le widget « {uw.get_display_title()} » a été masqué.')
        return redirect(request.POST.get('next', 'dashboard:home'))


class ShortcutCreateView(LoginRequiredMixin, View):
    template_name = 'dashboard/shortcut_form.html'

    def get(self, request):
        from django.shortcuts import render
        form = DashboardShortcutForm()
        return render(request, self.template_name, {
            'form': form,
            'page_title': 'Créer un raccourci',
            'action': 'create',
        })

    def post(self, request):
        form = DashboardShortcutForm(request.POST)
        if form.is_valid():
            shortcut = form.save(commit=False)
            shortcut.user = request.user
            shortcut.company = request.current_company
            order_max = DashboardShortcut.objects.filter(
                user=request.user, company=request.current_company
            ).count()
            shortcut.order = order_max
            shortcut.save()
            messages.success(request, 'Le raccourci a été créé.')
            return redirect('dashboard:home')
        from django.shortcuts import render
        return render(request, self.template_name, {
            'form': form,
            'page_title': 'Créer un raccourci',
            'action': 'create',
        })


class ShortcutUpdateView(LoginRequiredMixin, View):
    template_name = 'dashboard/shortcut_form.html'

    def get(self, request, pk):
        from django.shortcuts import render
        sc = get_object_or_404(DashboardShortcut, pk=pk, user=request.user)
        form = DashboardShortcutForm(instance=sc)
        return render(request, self.template_name, {
            'form': form, 'shortcut': sc,
            'page_title': f'Modifier — {sc.label}',
            'action': 'update',
        })

    def post(self, request, pk):
        sc = get_object_or_404(DashboardShortcut, pk=pk, user=request.user)
        form = DashboardShortcutForm(request.POST, instance=sc)
        if form.is_valid():
            form.save()
            messages.success(request, 'Le raccourci a été mis à jour.')
            return redirect('dashboard:home')
        from django.shortcuts import render
        return render(request, self.template_name, {
            'form': form, 'shortcut': sc,
            'page_title': f'Modifier — {sc.label}',
            'action': 'update',
        })


class ShortcutDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        sc = get_object_or_404(DashboardShortcut, pk=pk, user=request.user)
        label = sc.label
        sc.delete()
        messages.success(request, f'Le raccourci « {label} » a été supprimé.')
        return redirect(request.POST.get('next', 'dashboard:home'))


class SaveDashboardLayoutView(LoginRequiredMixin, View):
    def post(self, request):
        user = request.user
        company = request.current_company
        try:
            data = json.loads(request.body)
            widgets = data.get('widgets', [])
            profile = get_or_create_default_dashboard(user, company)
            for item in widgets:
                try:
                    uw = UserDashboardWidget.objects.get(
                        pk=item['widget_id'],
                        dashboard_profile__user=user,
                        dashboard_profile__company=company,
                    )
                    uw.position_x = int(item.get('position_x', uw.position_x))
                    uw.position_y = int(item.get('position_y', uw.position_y))
                    uw.width = int(item.get('width', uw.width))
                    uw.height = int(item.get('height', uw.height))
                    if 'is_visible' in item:
                        uw.is_visible = bool(item['is_visible'])
                    uw.save(update_fields=['position_x', 'position_y', 'width', 'height', 'is_visible'])
                except (UserDashboardWidget.DoesNotExist, KeyError, ValueError):
                    continue
            return JsonResponse({'status': 'ok', 'message': 'La disposition a été enregistrée.'})
        except (json.JSONDecodeError, Exception) as e:
            return JsonResponse({'status': 'error', 'message': 'Impossible de sauvegarder la disposition.'}, status=400)


class ResetDashboardView(LoginRequiredMixin, View):
    def post(self, request):
        reset_user_dashboard(request.user, request.current_company)
        messages.success(request, 'Votre dashboard a été réinitialisé.')
        return redirect('dashboard:home')
