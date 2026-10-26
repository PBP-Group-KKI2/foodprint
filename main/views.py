import datetime

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from .forms import ReportFilterForm, WasteReportForm
from .models import WasteReport


def show_landing(request):
    last_login = request.COOKIES.get('last_login', 'No active login session / Cookie not found')
    
    chart_data = {
        "labels": ['Food Waste', 'Plastic', 'Wood & Yard Waste', 'Paper & Cardboard', 'Other'],
         "values": [40, 20, 13, 11, 16],
         "colors": [
             "#4A5A2A",
             "#5E6F32", 
             "#B0BD8D", 
             "#D0D8B8", 
             "#E9EDDD" 
            ]
    }
    
    context = {
        "last_login": last_login,
        "chart_data": chart_data,
    }
    return render(request, "landing_page.html", context)

#ordinary user register an account
def register(request):
    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account created successfully. Please log in.")
        return redirect("main:login")

    context = {
        "name": "FoodPrint",
        "form": form,
    }
    return render(request, "register.html", context)

#login function
def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        response = redirect("main:landing")
        response.set_cookie('last_login', datetime.datetime.now().strftime('%d-%m %Y [%H:%M:%S]'))
        return response

    context = {
        "name": "Foodprint",
        "form": form,
    }
    return render(request, "login.html", context)

#logout function
def logout_user(request):
    logout(request)
    response = redirect("main:landing")
    response.delete_cookie('last_login')
    return response

#for future use, mainly serve as a yurisdiction of editor
def is_editor(user):
    return user.groups.filter(name='Editor').exists()


# ============================================================
# Reporting & Mapping
# ============================================================
MAX_PINS = 500


def _is_ajax(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _form_errors(form):
    return {field: [str(e) for e in errors] for field, errors in form.errors.items()}


def _filtered_reports(request):
    """Apply the filter form (search, type, severity, status, mine) to the queryset."""
    reports = WasteReport.objects.select_related("reporter")
    filter_form = ReportFilterForm(request.GET or None)

    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data["q"]:
            reports = reports.filter(
                Q(title__icontains=data["q"])
                | Q(description__icontains=data["q"])
                | Q(location_name__icontains=data["q"])
            )
        if data["waste_type"]:
            reports = reports.filter(waste_type=data["waste_type"])
        if data["severity"]:
            reports = reports.filter(severity=data["severity"])
        if data["status"]:
            reports = reports.filter(status=data["status"])
        if data["mine"] and request.user.is_authenticated:
            reports = reports.filter(reporter=request.user)

    return reports, filter_form


def _get_owned_report(request, pk):
    report = get_object_or_404(WasteReport, pk=pk)
    if not report.is_owned_by(request.user):
        raise PermissionDenied("You can only change your own reports.")
    return report


@require_GET
def report_map(request):
    """Main page: map with pins, filters, list, and the AJAX report form."""
    reports, filter_form = _filtered_reports(request)
    context = {
        "filter_form": filter_form if filter_form.is_bound else ReportFilterForm(),
        "report_form": WasteReportForm(),
        "reports": reports[:MAX_PINS],
    }
    return render(request, "reporting/map.html", context)


@require_GET
def report_list_json(request):
    """AJAX: filtered reports as JSON pins plus the rendered list HTML."""
    reports, _ = _filtered_reports(request)
    reports = list(reports[:MAX_PINS])
    html = render_to_string(
        "reporting/_report_list.html", {"reports": reports}, request=request
    )
    return JsonResponse(
        {
            "count": len(reports),
            "reports": [r.to_dict(request.user) for r in reports],
            "html": html,
        }
    )


@require_POST
def report_create(request):
    """AJAX: create a report from the map form without reloading the page."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Please log in to submit a report."}, status=401)

    form = WasteReportForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": _form_errors(form)}, status=400)

    report = form.save(commit=False)
    report.reporter = request.user
    report.save()
    return JsonResponse({"report": report.to_dict(request.user)}, status=201)


@require_GET
def report_detail(request, pk):
    report = get_object_or_404(WasteReport.objects.select_related("reporter"), pk=pk)
    context = {"report": report, "is_owner": report.is_owned_by(request.user)}
    return render(request, "reporting/report_detail.html", context)


@login_required
def report_update(request, pk):
    report = _get_owned_report(request, pk)
    form = WasteReportForm(request.POST or None, instance=report)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Report updated.")
        return redirect(report)

    return render(request, "reporting/report_form.html", {"form": form, "report": report})


@login_required
@require_POST
def report_delete(request, pk):
    report = _get_owned_report(request, pk)
    report_id = report.pk
    report.delete()

    if _is_ajax(request):
        return JsonResponse({"deleted": report_id})

    messages.success(request, "Report deleted.")
    return redirect("main:report_map")