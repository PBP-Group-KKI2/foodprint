from django.contrib import admin

from .models import Article, Comment, Favorite, Like


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("author", "content", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "created_at", "updated_at")
    list_filter = ("category",)
    search_fields = ("title", "summary", "content", "author__username")
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("article", "author", "created_at")
    search_fields = ("content", "author__username", "article__title")


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("article", "user", "created_at")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("article", "user", "created_at")
