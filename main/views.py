from django.shortcuts import render


def show_landing(request):
    return render(request, 'landing_page.html')