from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse


@login_required
def index(request):
    company = request.current_company
    return render(request, 'bi/index.html', {'page_title': 'Reporting', 'company': company})


@login_required
def report_list(request):
    company = request.current_company
    return render(request, 'bi/report_list.html', {
        'page_title': 'Reporting',
        'company': company,
    })


def _report_view(module_name, title):
    @login_required
    def view(request):
        company = request.current_company
        return render(request, 'bi/index.html', {
            'page_title': f'Reporting — {title}',
            'company': company,
            'active_module': module_name,
        })
    view.__name__ = f'report_{module_name}'
    return view


commercial = _report_view('commercial', 'Commercial')
finance = _report_view('finance', 'Finance')
accounting = _report_view('accounting', 'Comptabilité')
btp = _report_view('btp', 'BTP')
stocks = _report_view('stocks', 'Stocks')
ecommerce = _report_view('ecommerce', 'E-commerce')
commerce = _report_view('commerce', 'Commerce')
production = _report_view('production', 'Production')
hr = _report_view('hr', 'RH')
websites = _report_view('websites', 'Sites web')
support = _report_view('support', 'Support')


@login_required
def export(request, module, format):
    return HttpResponse(
        f'Export {format.upper()} — {module} (à implémenter)',
        content_type='text/plain'
    )


