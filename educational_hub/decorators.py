from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Article

RATE_LIMIT_MESSAGE = "You're doing that too many times. Please wait a moment and try again."


def article_manager_required(view):
    """Log in, then allow only the article's author or staff. The view receives the article."""
    @wraps(view)
    def wrapper(request, pk, *args, **kwargs):
        article = get_object_or_404(Article, pk=pk)
        if not article.can_be_managed_by(request.user):
            raise PermissionDenied("You can only change your own articles.")
        return view(request, article, *args, **kwargs)
    return login_required(wrapper)


def rate_limit(scope, limit, window_seconds):
    """Allow at most `limit` POSTs per user (or IP when logged out) in a rolling window."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method == "POST":
                who = request.user.pk if request.user.is_authenticated else request.META.get("REMOTE_ADDR", "anon")
                key = f"eh-rate-{scope}-{who}"
                # add() starts the window only once; incr() is atomic on Django's cache backends.
                cache.add(key, 0, window_seconds)
                try:
                    count = cache.incr(key)
                except ValueError:  # the window expired between add() and incr()
                    cache.set(key, 1, window_seconds)
                    count = 1
                if count > limit:
                    return _rate_limited(request)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def _rate_limited(request):
    if request.headers.get("HX-Request") == "true":
        return HttpResponse(RATE_LIMIT_MESSAGE, status=429, content_type="text/plain")
    messages.error(request, RATE_LIMIT_MESSAGE)
    referer = request.META.get("HTTP_REFERER", "")
    if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(referer)
    return redirect("education:article_list")
