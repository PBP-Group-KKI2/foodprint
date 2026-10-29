from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_POST

from .forms import ArticleFilterForm, ArticleForm, CommentForm
from .models import Article, Comment, Favorite, Like

ARTICLES_PER_PAGE = 9
COMMENT_COOLDOWN_SECONDS = 10
DUPLICATE_COMMENT_WINDOW = timedelta(seconds=60)


# ============================================================
# Helpers
# ============================================================

def _is_htmx(request):
    """HTMX history restores (browser back button) need the full page, not a partial."""
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


def _articles_for(user):
    """Articles with like/favorite/comment counts and the user's own like/save state."""
    articles = Article.objects.select_related("author__profile").annotate(
        like_count=Count("likes", distinct=True),
        favorite_count=Count("favorites", distinct=True),
        comment_count=Count("comments", distinct=True),
    ).order_by("-created_at", "-pk")  # Meta.ordering is ignored once Count() is used
    if user.is_authenticated:
        articles = articles.annotate(
            is_liked=Exists(Like.objects.filter(article=OuterRef("pk"), user=user)),
            is_favorited=Exists(Favorite.objects.filter(article=OuterRef("pk"), user=user)),
        )
    return articles


def _get_manageable_article(request, pk):
    """Author or staff only. Anyone else gets a 403, even by typing the URL directly."""
    article = get_object_or_404(Article, pk=pk)
    if not article.can_be_managed_by(request.user):
        raise PermissionDenied("You can only change your own articles.")
    return article


def _login_required_response(request, next_url):
    """HTMX would swap a normal redirect into the page, so it gets HX-Redirect instead."""
    response = redirect_to_login(next_url)
    if _is_htmx(request):
        htmx_response = HttpResponse(status=401)
        htmx_response["HX-Redirect"] = response["Location"]
        return htmx_response
    return response


def _comment_context(request, article, form=None):
    return {
        "article": article,
        "comments": article.comments.select_related("author"),
        "comment_form": form or CommentForm(),
    }


# ============================================================
# Article list, saved list, detail
# ============================================================

def _render_article_list(request, articles, is_saved_view):
    filter_form = ArticleFilterForm(request.GET or None)
    is_filtered = False

    if filter_form.is_valid():
        data = filter_form.cleaned_data
        if data["q"]:
            is_filtered = True
            articles = articles.filter(
                Q(title__icontains=data["q"])
                | Q(summary__icontains=data["q"])
                | Q(content__icontains=data["q"])
            )
        if data["category"]:
            is_filtered = True
            articles = articles.filter(category=data["category"])

    page_obj = Paginator(articles, ARTICLES_PER_PAGE).get_page(request.GET.get("page"))
    context = {
        "filter_form": filter_form if filter_form.is_bound else ArticleFilterForm(),
        "page_obj": page_obj,
        "is_filtered": is_filtered,
        "is_saved_view": is_saved_view,
        "categories": Article.Category.choices,
        "active_category": request.GET.get("category", ""),
    }

    template = "educational_hub/_article_results.html" if _is_htmx(request) else "educational_hub/article_list.html"
    response = render(request, template, context)
    # Same URL returns a partial or a full page, so caches must tell them apart.
    patch_vary_headers(response, ["HX-Request"])
    return response


@require_GET
def article_list(request):
    return _render_article_list(request, _articles_for(request.user), is_saved_view=False)


@login_required
@require_GET
def saved_articles(request):
    articles = _articles_for(request.user).filter(is_favorited=True)
    return _render_article_list(request, articles, is_saved_view=True)


@require_GET
def article_detail(request, pk):
    article = get_object_or_404(_articles_for(request.user), pk=pk)
    context = {
        **_comment_context(request, article),
        "can_manage": article.can_be_managed_by(request.user),
    }
    return render(request, "educational_hub/article_detail.html", context)


# ============================================================
# Create, edit, delete
# ============================================================

def _save_article_form(request, form, success_message):
    """Returns None if two identical submissions race past the form's title check."""
    article = form.save(commit=False)
    if article.author_id is None:
        article.author = request.user
    try:
        with transaction.atomic():
            article.save()
    except IntegrityError:
        form.add_error("title", "You already published an article with this title.")
        return None
    messages.success(request, success_message)
    return redirect(article)


@login_required
def article_create(request):
    form = ArticleForm(request.POST or None, author=request.user)

    if request.method == "POST" and form.is_valid():
        response = _save_article_form(request, form, "Article published.")
        if response:
            return response

    return render(request, "educational_hub/article_form.html", {"form": form})


@login_required
def article_update(request, pk):
    article = _get_manageable_article(request, pk)
    form = ArticleForm(request.POST or None, instance=article)

    if request.method == "POST" and form.is_valid():
        response = _save_article_form(request, form, "Article updated.")
        if response:
            return response

    return render(request, "educational_hub/article_form.html", {"form": form, "article": article})


@login_required
def article_delete(request, pk):
    """GET shows a confirmation page; only a POST actually deletes."""
    article = _get_manageable_article(request, pk)

    if request.method == "POST":
        article.delete()  # comments, likes, and favorites are removed by CASCADE
        messages.success(request, "Article deleted.")
        return redirect("education:article_list")

    article = _articles_for(request.user).get(pk=article.pk)
    return render(request, "educational_hub/article_confirm_delete.html", {"article": article})


# ============================================================
# Likes, favorites, comments
# ============================================================

def _toggle_reaction(request, pk, model):
    article = get_object_or_404(Article, pk=pk)
    if not request.user.is_authenticated:
        return _login_required_response(request, article.get_absolute_url())

    # The unique constraint keeps this to one row per user, even for simultaneous requests.
    reaction, created = model.objects.get_or_create(article=article, user=request.user)
    if not created:
        reaction.delete()

    if _is_htmx(request):
        article = _articles_for(request.user).get(pk=pk)
        return render(request, "educational_hub/_reaction_buttons.html", {"article": article})
    return redirect(article)


@require_POST
def toggle_like(request, pk):
    return _toggle_reaction(request, pk, Like)


@require_POST
def toggle_favorite(request, pk):
    return _toggle_reaction(request, pk, Favorite)


@require_POST
def comment_create(request, pk):
    article = get_object_or_404(Article, pk=pk)
    if not request.user.is_authenticated:
        return _login_required_response(request, article.get_absolute_url())

    form = CommentForm(request.POST)
    saved = False

    if form.is_valid():
        content = form.cleaned_data["content"]
        is_duplicate = Comment.objects.filter(
            article=article,
            author=request.user,
            content=content,
            created_at__gte=timezone.now() - DUPLICATE_COMMENT_WINDOW,
        ).exists()

        if is_duplicate:
            form.add_error(None, "You just posted this comment.")
        # cache.add fails if the key already exists, which gives a per-user cooldown.
        elif not cache.add(f"eh-comment-cooldown-{request.user.pk}", True, COMMENT_COOLDOWN_SECONDS):
            form.add_error(None, f"Please wait {COMMENT_COOLDOWN_SECONDS} seconds between comments.")
        else:
            comment = form.save(commit=False)
            comment.article = article
            comment.author = request.user
            comment.save()
            saved = True

    if _is_htmx(request):
        context = _comment_context(request, article, None if saved else form)
        context["comment_status"] = "Comment posted." if saved else ""
        return render(request, "educational_hub/_comment_section.html", context)

    if saved:
        messages.success(request, "Comment posted.")
    else:
        errors = [e for field_errors in form.errors.values() for e in field_errors]
        messages.error(request, " ".join(errors) or "Your comment could not be posted.")
    return redirect(f"{article.get_absolute_url()}#comments")
