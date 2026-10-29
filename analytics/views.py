from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count
from main.models import WasteReport
from analytics.models import DashboardPreset

# Create your views here.
def show_analytics(request):
    # Applying the preset filters
    base_qs = WasteReport.objects.all()

    preset_id = request.GET.get('preset')
    if preset_id and request.user.is_authenticated:
        try:
            active_preset = DashboardPreset.objects.get(id=preset_id, user=request.user)
            if active_preset.city:
                base_qs = base_qs.filter(city=active_preset.city)
            if active_preset.district:
                base_qs = base_qs.filter(district=active_preset.district)
            if active_preset.waste_type:
                base_qs = base_qs.filter(waste_type=active_preset.waste_type)
            if active_preset.severity:
                base_qs = base_qs.filter(severity=active_preset.severity)
        except DashboardPreset.DoesNotExist:
            pass

    # Retrieve the total count for KPI
    waste_reports = base_qs.count()
    resolved_reports = base_qs.filter(status="RESOLVED").count()
    
    # Query to retrieve total waste reports per city 
    city_qs = base_qs.exclude(city="").values('city').annotate(total=Count('id')).order_by('-total')
    city_labels = [item['city'] for item in city_qs]
    city_values = [item['total'] for item in city_qs]

    # Query to retrieve total waste reports per district
    district_qs = base_qs.exclude(district="").values('district').annotate(total=Count('id')).order_by('-total')
    district_labels = [item['district'] for item in district_qs]
    district_values = [item['total'] for item in district_qs]
    
    # Query to retrieve waste by type
    type_qs = base_qs.values('waste_type').annotate(total=Count('id'))
    type_choices = dict(WasteReport.WasteType.choices)
    type_labels = [type_choices.get(item['waste_type'], item['waste_type']) for item in type_qs]
    type_values = [item['total'] for item in type_qs]

    # Query to retrieve serevity
    severity_qs = base_qs.values('severity').annotate(total=Count('id'))
    severity_choices = dict(WasteReport.Severity.choices)
    severity_labels = [severity_choices.get(item['severity'], item['severity']) for item in severity_qs]
    severity_values = [item['total'] for item in severity_qs]

    # Query to retrieve available cities and districts (used for preset)
    available_cities = WasteReport.objects.exclude(city="").values_list('city', flat=True).distinct().order_by('city')
    available_districts = WasteReport.objects.exclude(district="").values_list('district', flat=True).distinct().order_by('district')
    
    # Retrieve waste types and severities (also for preset)
    waste_types = WasteReport.WasteType.choices
    severities = WasteReport.Severity.choices

    user_presets = DashboardPreset.objects.filter(user=request.user) if request.user.is_authenticated else []

    context = {
        'page_title' : 'Organization Analytics Dashboard',
        'available_cities': available_cities,
        'available_districts': available_districts,
        'waste_types': waste_types,
        'severities': severities,
        'presets': user_presets,
        'waste_reports': waste_reports,
        'resolved_reports': resolved_reports,
        'city_labels': city_labels,
        'city_values': city_values,
        'district_labels': district_labels,
        'district_values': district_values,
        'type_labels': type_labels,
        'type_values': type_values,
        'severity_labels': severity_labels,
        'severity_values': severity_values,

    }

    return render(request, "analytics/analytics_dashboard.html", context)

def save_preset(request):
    if request.method == "POST" and request.user.is_authenticated:
        DashboardPreset.objects.create(
            user=request.user,
            name=request.POST.get('name'),
            city=request.POST.get('city'),
            district=request.POST.get('district'),
            waste_type=request.POST.get('waste_type'),
            severity=request.POST.get('severity')
        )
    return redirect('analytics:show_analytics')

def delete_preset(request, preset_id):
    if request.method == "POST" and request.user.is_authenticated:
        preset = get_object_or_404(DashboardPreset, id=preset_id, user=request.user)
        preset.delete()
    return redirect('analytics:show_analytics')