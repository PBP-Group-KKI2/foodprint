from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.urls import reverse
from django.utils.text import Truncator


class Article(models.Model):

    class Category(models.TextChoices):
        BASICS = "BASICS", "Food waste basics"
        SORTING = "SORTING", "Sorting & separation"
        COMPOSTING = "COMPOSTING", "Composting"
        REDUCING = "REDUCING", "Reducing waste at home"
        COMMUNITY = "COMMUNITY", "Community & policy"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="articles",
    )
    title = models.CharField(max_length=150)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.BASICS
    )
    summary = models.CharField(
        max_length=300,
        blank=True,
        help_text="Optional one- or two-sentence preview shown on the article list.",
    )
    # Plain text only; templates escape it so users can't inject HTML.
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["-created_at"], name="eh_article_created_idx")]
        constraints = [
            # Stops duplicate articles from a double-clicked submit button.
            models.UniqueConstraint(
                fields=["author", "title"], name="eh_unique_article_title_per_author"
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("education:article_detail", args=[self.pk])

    def is_owned_by(self, user):
        return user.is_authenticated and user.pk == self.author_id

    def can_be_managed_by(self, user):
        """Owners and staff (Django admin users) may edit or delete an article."""
        return self.is_owned_by(user) or (user.is_authenticated and user.is_staff)

    @property
    def excerpt(self):
        return self.summary or Truncator(self.content).chars(180)

    @property
    def author_role_label(self):
        """Profile role ('Organization', 'Official/Government', ...) or '' if none."""
        try:
            profile = self.author.profile
        except ObjectDoesNotExist:
            return ""
        return profile.get_role_display()

    @property
    def was_edited(self):
        return (self.updated_at - self.created_at).total_seconds() > 60


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.author} on {self.article}"


class Like(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["article", "user"], name="eh_unique_like"),
        ]

    def __str__(self):
        return f"{self.user} likes {self.article}"


class Favorite(models.Model):
    """A user's personal saved article (separate from a public like)."""

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="favorites")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="article_favorites",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["article", "user"], name="eh_unique_favorite"),
        ]

    def __str__(self):
        return f"{self.user} saved {self.article}"
