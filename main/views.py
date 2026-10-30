import datetime

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_protect

from .forms import ReportFilterForm, WasteReportForm, WasteReportAdminForm, ExtendedRegisterForm
from .models import WasteReport, Profile

from django.utils.http import url_has_allowed_host_and_scheme
from rewards.views import award_points
from educational_hub.models import Article
from task_dispatch.models import is_dispatcher


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
        "report_count": WasteReport.objects.count(),
        "resolved_count": WasteReport.objects.filter(status=WasteReport.Status.RESOLVED).count(),
        "latest_articles": Article.objects.select_related("author")[:3],
        "can_dispatch": is_dispatcher(request.user),
    }
    return render(request, "landing_page.html", context)

#ordinary user register an account
@csrf_protect
def register(request): 
    if request.method == 'POST':
        form = ExtendedRegisterForm(request.POST)  
        if form.is_valid():
            user = form.save()
            
            selected_role = form.cleaned_data.get('role')
            user_email = form.cleaned_data.get('email')
            
            Profile.objects.create(
                user=user,
                role=selected_role,
                email=user_email
            )
            
            login(request, user)
            return redirect('main:dashboard_router')
    else:
        form = ExtendedRegisterForm()  
        
    return render(request, 'register.html', {'form': form})

#login function
def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)

    # login_required adds ?next=; only same-site paths are kept to avoid open redirects
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = ""

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        response = redirect(next_url or "main:landing")
        response.set_cookie('last_login', datetime.datetime.now().strftime('%d-%m %Y [%H:%M:%S]'))
        return response

    context = {
        "name": "Foodprint",
        "form": form,
        "next": next_url,
        "login_required_notice": request.method == "GET" and bool(next_url),
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
    """Apply the filter form (search, type, severity, status, city, district, mine)."""
    reports = WasteReport.objects.select_related("reporter")
    filter_form = ReportFilterForm(request.GET or None)

    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data["q"]:
            reports = reports.filter(
                Q(title__icontains=data["q"])
                | Q(description__icontains=data["q"])
                | Q(location_name__icontains=data["q"])
                | Q(city__icontains=data["q"])
                | Q(district__icontains=data["q"])
            )
        if data["waste_type"]:
            reports = reports.filter(waste_type=data["waste_type"])
        if data["severity"]:
            reports = reports.filter(severity=data["severity"])
        if data["status"]:
            reports = reports.filter(status=data["status"])
        if data["city"]:
            reports = reports.filter(city=data["city"])
        if data["district"]:
            reports = reports.filter(district=data["district"])
        if data["mine"] and request.user.is_authenticated:
            reports = reports.filter(reporter=request.user)

    return reports, filter_form

def _can_manage(user, report):
    """The reporter, or an admin (staff), may edit or delete a report."""
    return report.is_owned_by(user) or (user.is_authenticated and user.is_staff)


def _get_manageable_report(request, pk):
    report = get_object_or_404(WasteReport, pk=pk)
    if not _can_manage(request.user, report):
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
    award_points(request.user)          # +5 points
    return JsonResponse({"report": report.to_dict(request.user)}, status=201)


@require_GET
def report_detail(request, pk):
    report = get_object_or_404(WasteReport.objects.select_related("reporter"), pk=pk)
    context = {"report": report, "can_manage": _can_manage(request.user, report)}
    return render(request, "reporting/report_detail.html", context)


@login_required
def report_update(request, pk):
    report = _get_manageable_report(request, pk)
    # Admins also get the Status field, so they can mark reports as resolved.
    form_class = WasteReportAdminForm if request.user.is_staff else WasteReportForm
    form = form_class(request.POST or None, instance=report)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Report updated.")
        return redirect(report)

    return render(request, "reporting/report_form.html", {"form": form, "report": report})


@login_required
@require_POST
def report_delete(request, pk):
    report = _get_manageable_report(request, pk)
    report_id = report.pk
    report.delete()

    if _is_ajax(request):
        return JsonResponse({"deleted": report_id})

    messages.success(request, "Report deleted.")
    return redirect("main:report_map")

# ============================================================
# PROFILE
# ============================================================

@login_required
def organization_dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.role != 'ORGANIZATION':
        return HttpResponseForbidden("Access denied.")
    context = {'title': 'Organization Portal'}
    return render(request, 'dashboards/organization.html', context)


@login_required
def dashboard_router(request):
    """Directing users to the appropriate dashboard based on their role"""

    from .models import Profile
    profile, _ = Profile.objects.get_or_create(
        user=request.user,
        defaults={'role': 'USERS'} 
    )
        
    user_role = profile.role

    if user_role == 'OFFICIAL':
        return redirect('main:official_dashboard')
    elif user_role == 'ORGANIZATION':
        return redirect('main:organization_dashboard')
    else:
        return redirect('main:users_dashboard')

@login_required
def official_dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.role != 'OFFICIAL':
        return HttpResponseForbidden("You don't have access to this page.")
    
    # special data logic for official user
    context = {'title': 'Official Management Console'}
    return render(request, 'dashboards/official.html', context)

@login_required
def users_dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.role != 'USERS':
        return HttpResponseForbidden("Access denied.")
    
    context = {
        'title': 'Users Portal',
        'profile': profile, 
    }
    return render(request, 'dashboards/users.html', context)

@login_required
def update_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    user_role = profile.role

    if request.method == 'POST':
        password_form = PasswordChangeForm(request.user, request.POST)
        
        input_email = request.POST.get('email')
        
        if user_role == 'USERS':
            input_username = request.POST.get('username')
            if input_username:
                if User.objects.exclude(pk=request.user.pk).filter(username=input_username).exists():
                    messages.error(request, 'That username is already taken.')
                    return render(request, 'profiles/update.html', {
                        'profile': profile,
                        'user_role': user_role,
                        'password_form': password_form
                    })
                request.user.username = input_username
        
        if input_email:
            request.user.email = input_email
            profile.email = input_email

        if request.POST.get('old_password'):
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been successfully updated!')
            else:
                messages.error(request, 'Failed to update password. Please double-check your input.')
                return render(request, 'profiles/update.html', {
                    'profile': profile, 
                    'user_role': user_role, 
                    'password_form': password_form
                })

        request.user.save()
        profile.save()
        
        messages.success(request, 'Your profile has been successfully updated!')
        return redirect('main:dashboard_router')

    else:
        password_form = PasswordChangeForm(request.user)

    context = {
        'profile': profile,
        'user_role': user_role,
        'password_form': password_form
    }
    return render(request, 'profiles/update.html', context)

def register_view(request):
    if request.method == 'POST':
        form = ExtendedRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            selected_role = form.cleaned_data.get('role')
            user_email = form.cleaned_data.get('email')
            point_deposit = form.cleaned_data.get('point_deposit')  #store reward points
            
            Profile.objects.create(
                user=user,
                role=selected_role,
                email=user_email,
                point=point_deposit,
            )
            
            login(request, user)
            
            return redirect('dashboard_router')
    else:
        form = ExtendedRegisterForm()
        
    return render(request, 'registration/register.html', {'form': form})

# ============================================================
# REWARD
# ============================================================

@login_required
def show_reward(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    return render(request, "reward.html", {"profile": profile})


@login_required
@require_POST
def toggle_rank(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    profile.show_rank = not profile.show_rank
    profile.save(update_fields=["show_rank"])

    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = "main:landing"
    return redirect(next_url)
