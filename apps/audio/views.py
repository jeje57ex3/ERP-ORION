from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from .models import Equipment, AudioEvent, EquipmentReservation, Technician
from .forms import EquipmentForm, AudioEventForm, ReservationForm, TechnicianForm


@login_required
def index(request):
    return redirect('audio:event_list')


# --- EVENTS ---

@login_required
def event_list(request):
    company = request.current_company
    qs = AudioEvent.objects.filter(company=company).select_related('customer')
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(venue__icontains=search))
    confirmed = AudioEvent.objects.filter(company=company, status='confirmed').count()
    in_progress = AudioEvent.objects.filter(company=company, status='in_progress').count()
    total_amount = AudioEvent.objects.filter(company=company).aggregate(Sum('estimated_amount'))['estimated_amount__sum'] or 0
    return render(request, 'audio/event_list.html', {
        'events': qs, 'status': status, 'search': search,
        'status_choices': AudioEvent.STATUS_CHOICES,
        'confirmed': confirmed, 'in_progress': in_progress, 'total_amount': total_amount,
    })


@login_required
def event_detail(request, pk):
    company = request.current_company
    event = get_object_or_404(AudioEvent, pk=pk, company=company)
    reservations = EquipmentReservation.objects.filter(company=company, event=event)
    assignments = event.technician_assignments.select_related('technician').all()
    return render(request, 'audio/event_detail.html', {
        'event': event, 'reservations': reservations, 'assignments': assignments,
    })


@login_required
def event_create(request):
    company = request.current_company
    form = AudioEventForm(company=company)
    if request.method == 'POST':
        form = AudioEventForm(request.POST, company=company)
        if form.is_valid():
            event = form.save(commit=False)
            event.company = company
            event.created_by = request.user
            event.save()
            messages.success(request, f'Événement « {event.name} » créé.')
            return redirect('audio:event_detail', pk=event.pk)
    return render(request, 'audio/event_form.html', {'form': form, 'action': 'create'})


@login_required
def event_edit(request, pk):
    company = request.current_company
    event = get_object_or_404(AudioEvent, pk=pk, company=company)
    form = AudioEventForm(instance=event, company=company)
    if request.method == 'POST':
        form = AudioEventForm(request.POST, instance=event, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Événement mis à jour.')
            return redirect('audio:event_detail', pk=pk)
    return render(request, 'audio/event_form.html', {'form': form, 'event': event, 'action': 'edit'})


# --- EQUIPMENT ---

@login_required
def equipment_list(request):
    company = request.current_company
    qs = Equipment.objects.filter(company=company)
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(reference__icontains=search) | Q(brand__icontains=search))
    total = Equipment.objects.filter(company=company).count()
    available = Equipment.objects.filter(company=company, status='available').count()
    return render(request, 'audio/equipment_list.html', {
        'equipment_list': qs, 'status': status, 'search': search,
        'status_choices': Equipment.STATUS_CHOICES,
        'total': total, 'available': available,
    })


@login_required
def equipment_detail(request, pk):
    company = request.current_company
    equipment = get_object_or_404(Equipment, pk=pk, company=company)
    reservations = EquipmentReservation.objects.filter(company=company, equipment=equipment).order_by('-start_date')[:10]
    return render(request, 'audio/equipment_detail.html', {'equipment': equipment, 'reservations': reservations})


@login_required
def equipment_create(request):
    company = request.current_company
    form = EquipmentForm(company=company)
    if request.method == 'POST':
        form = EquipmentForm(request.POST, company=company)
        if form.is_valid():
            eq = form.save(commit=False)
            eq.company = company
            eq.save()
            messages.success(request, f'Matériel « {eq.name} » créé.')
            return redirect('audio:equipment_detail', pk=eq.pk)
    return render(request, 'audio/equipment_form.html', {'form': form, 'action': 'create'})


@login_required
def equipment_edit(request, pk):
    company = request.current_company
    equipment = get_object_or_404(Equipment, pk=pk, company=company)
    form = EquipmentForm(instance=equipment, company=company)
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Matériel mis à jour.')
            return redirect('audio:equipment_detail', pk=pk)
    return render(request, 'audio/equipment_form.html', {'form': form, 'equipment': equipment, 'action': 'edit'})


# --- RESERVATIONS ---

@login_required
def reservation_list(request):
    company = request.current_company
    qs = EquipmentReservation.objects.filter(company=company).select_related('equipment', 'customer', 'event')
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    return render(request, 'audio/reservation_list.html', {
        'reservations': qs, 'status': status,
        'status_choices': EquipmentReservation.STATUS_CHOICES,
    })


@login_required
def reservation_create(request):
    company = request.current_company
    form = ReservationForm(company=company)
    if request.method == 'POST':
        form = ReservationForm(request.POST, company=company)
        if form.is_valid():
            res = form.save(commit=False)
            res.company = company
            res.save()
            messages.success(request, 'Réservation créée.')
            return redirect('audio:reservation_list')
    return render(request, 'audio/reservation_form.html', {'form': form, 'action': 'create'})


# --- TECHNICIANS ---

@login_required
def technician_list(request):
    company = request.current_company
    technicians = Technician.objects.filter(company=company)
    return render(request, 'audio/technician_list.html', {'technicians': technicians})


@login_required
def technician_create(request):
    company = request.current_company
    form = TechnicianForm()
    if request.method == 'POST':
        form = TechnicianForm(request.POST)
        if form.is_valid():
            tech = form.save(commit=False)
            tech.company = company
            tech.save()
            messages.success(request, f'Technicien « {tech.name} » ajouté.')
            return redirect('audio:technician_list')
    return render(request, 'audio/technician_form.html', {'form': form})


