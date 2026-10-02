from django.shortcuts import render


def show_landing(request):
    chart_data = {
            'labels': ['Food Waste', 'Plastic', 'Wood & Yard Waste', 'Paper & Cardboard', 'Other'],
            'values': [40, 20, 13, 11, 16],
            'colors': [
                '#4A5A2A', # Dark Green (Food)
                '#5E6F32', # Blue (Plastic)
                '#B0BD8D', # Brown (Wood)
                '#D0D8B8', # Yellow/Orange (Paper)
                '#E9EDDD'  # Grey (Other)]
            ]
        }

    context = {
        'chart_data': chart_data,
    }
    
    return render(request, 'landing_page.html', context)