from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from main.models import WasteReport

from .forms import PendingFilterForm, TaskCloseForm, TaskUpdateForm
from .models import CollectionTask, is_dispatcher

REPORTS_PER_PAGE = 20

SEVERITY_RANK = Case(
    When(severity=WasteReport.Severity.HIGH, then=Value(0)),
    When(severity=WasteReport.Severity.MEDIUM, then=Value(1)),
    default=Value(2),
    output_field=IntegerField(),
)
SORT_ORDERS = {
    "severity": [SEVERITY_RANK, "created_at"],
    "oldest": ["created_at"],
    "newest": ["-created_at"],
}


# ============================================================
# Helpers
# ============================================================

def dispatcher_required(view):
    """Login first, then only officials and staff get through."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_dispatcher(request.user):
            raise PermissionDenied("Only officials can manage collection tasks.")
        return view(request, *args, **kwargs)
    return login_required(wrapper)


def _get_manageable_task(request, pk):
    task = get_object_or_404(CollectionTask.objects.select_related("report"), pk=pk)
    if not task.can_be_managed_by(request.user):
        raise PermissionDenied("You can only change tasks you claimed.")
    return task


def _closed_task_redirect(request, task):
    """Closed tasks are read-only. Returns a redirect back to the task, or None if open."""
    if task.is_open:
        return None
    messages.error(request, "This task is already closed.")
    return redirect(task)


# ============================================================
# Pending reports & my tasks
# ============================================================

@dispatcher_required
@require_GET
def pending_reports(request):
    """Reports nobody has claimed yet, with filters and sorting."""
    reports = WasteReport.objects.select_related("reporter").filter(
        status=WasteReport.Status.REPORTED, task__isnull=True
    )
    filter_form = PendingFilterForm(request.GET or None)
    sort = "severity"

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
        if data["city"]:
            reports = reports.filter(city=data["city"])
        sort = data["sort"] or sort

    reports = reports.order_by(*SORT_ORDERS[sort])
    page_obj = Paginator(reports, REPORTS_PER_PAGE).get_page(request.GET.get("page"))

    # Keep the filters in the pagination links.
    query = request.GET.copy()
    query.pop("page", None)

    context = {
        "filter_form": filter_form if filter_form.is_bound else PendingFilterForm(),
        "page_obj": page_obj,
        "query_string": query.urlencode(),
        "open_task_count": request.user.collection_tasks.exclude(
            status=CollectionTask.Status.CLOSED
        ).count(),
    }
    return render(request, "task_dispatch/pending_list.html", context)


@dispatcher_required
@require_GET
def my_tasks(request):
    show_closed = request.GET.get("show") == "closed"
    tasks = request.user.collection_tasks.select_related("report")
    if show_closed:
        tasks = tasks.filter(status=CollectionTask.Status.CLOSED).order_by("-closed_at")
    else:
        # Earliest pickup first; tasks without a date go last.
        tasks = tasks.exclude(status=CollectionTask.Status.CLOSED).order_by(
            "scheduled_for", "claimed_at"
        )

    context = {"tasks": tasks, "show_closed": show_closed}
    return render(request, "task_dispatch/my_tasks.html", context)


# ============================================================
# Claim, detail, update, close, release
# ============================================================

@dispatcher_required
@require_POST
def claim_report(request, report_pk):
    report = get_object_or_404(WasteReport, pk=report_pk)
    task = CollectionTask.claim(report, request.user)

    if task is None:
        messages.error(request, f"“{report.title}” was already claimed or is no longer pending.")
        return redirect("dispatch:pending_reports")

    messages.success(request, f"You claimed “{report.title}”. Add a pickup date when you know it.")
    return redirect(task)


@dispatcher_required
@require_GET
def task_detail(request, pk):
    task = get_object_or_404(
        CollectionTask.objects.select_related("report__reporter", "official"), pk=pk
    )
    context = {"task": task, "can_manage": task.can_be_managed_by(request.user)}
    return render(request, "task_dispatch/task_detail.html", context)


@dispatcher_required
def task_update(request, pk):
    task = _get_manageable_task(request, pk)
    closed = _closed_task_redirect(request, task)
    if closed:
        return closed

    form = TaskUpdateForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Task updated.")
        return redirect(task)

    return render(request, "task_dispatch/task_form.html", {"form": form, "task": task})


@dispatcher_required
def task_close(request, pk):
    """GET shows the closing form; POST closes the task and resolves the report."""
    task = _get_manageable_task(request, pk)
    closed = _closed_task_redirect(request, task)
    if closed:
        return closed

    form = TaskCloseForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        task.close(form.cleaned_data["closing_note"])
        messages.success(request, f"Task closed. “{task.report.title}” is marked as resolved.")
        return redirect(task)

    return render(request, "task_dispatch/task_close.html", {"form": form, "task": task})


@dispatcher_required
@require_POST
def task_release(request, pk):
    """Un-claim: the report goes back to the pending list for someone else."""
    task = _get_manageable_task(request, pk)
    closed = _closed_task_redirect(request, task)
    if closed:
        return closed

    title = task.report.title
    task.release()
    messages.success(request, f"You released “{title}”. It is back on the pending list.")
    return redirect("dispatch:my_tasks")
