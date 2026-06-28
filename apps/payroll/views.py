from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def index(request):
    company = request.current_company
    return render(request, 'payroll/index.html', {'page_title': 'Paie', 'company': company})


