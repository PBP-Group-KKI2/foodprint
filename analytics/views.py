from django.shortcuts import render
from django.db.models import Count
#from main.models import WasteReport

# Create your views here.
def show_dashboard(request):
    
    """
    NOTE: This is for later use when the module is merged with the reporting module

    # Query to find total waste reports per city 
    city_qs = WasteReport.objects.exclude(city="").values('city').annotate(total=Count('id'))
    city_labels = [item['city'] for item in city_qs]
    city_values = [item['total'] for item in city_qs]

    # Query to find total waste reports per district
    district_qs = WasteReport.objects.exclude(district="").values('district').annotate(total=Count('id'))
    district_labels = [item['district'] for item in district_qs]
    district_values = [item['total'] for item in district_qs]
    
    # Query to find waste by type
    
    selected_city = request.GET.get('city', None)
    
    type_qs = WasteReport.objects.all()
    if selected_city:
        type_qs = type_qs.filter(city=selected_city)
    
    type_qs = type_qs.values('waste_type').annotate(total=Count('id'))
    type_labels = [item['waste_type'] for item in type_qs]
    type_values = [item['total'] for item in type_qs]
    
    """
    
    # Temporary dummy values
    city_labels = ['South Jakarta', 'Depok', 'Central Jakarta', 'East Jakarta']
    city_values = [45, 20, 15, 30]

    district_labels = ['Kebayoran Baru', 'Beji', 'Menteng', 'Tebet', 'Cilandak']
    district_values = [15, 12, 10, 8, 20]

    type_labels = ['FOOD', 'PACKAGING', 'MIXED', 'OTHER']
    type_values = [50, 30, 20, 10]

    severity_labels = ['Low', 'Medium', 'High', 'Critical']
    severity_values = [60, 45, 25, 20]

    context = {
        "page_title" : "Organization Dashboard",
        'city_labels': city_labels,
        'city_values': city_values,
        'district_labels': district_labels,
        'district_values': district_values,
        'type_labels': type_labels,
        'type_values': type_values,
        'severity_labels': severity_labels,
        'severity_values': severity_values,
        #'selected_city': selected_city,
    }

    return render(request, "analytics/dashboard.html", context)
