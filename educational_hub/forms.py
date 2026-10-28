from django import forms

from .models import Article, Comment


class ArticleForm(forms.ModelForm):
    """No `author` field on purpose: the view sets it from the logged-in user."""

    class Meta:
        model = Article
        fields = ["title", "category", "summary", "content"]
        labels = {"summary": "Summary", "content": "Article"}
        widgets = {
            "title": forms.TextInput(
                attrs={"placeholder": "e.g. How to tell compostable scraps apart", "maxlength": 150}
            ),
            "summary": forms.Textarea(
                attrs={"rows": 2, "maxlength": 300, "placeholder": "A short preview for the article list"}
            ),
            "content": forms.Textarea(
                attrs={"rows": 16, "placeholder": "Write your article. Leave a blank line between paragraphs."}
            ),
        }

    def __init__(self, *args, author=None, **kwargs):
        super().__init__(*args, **kwargs)
        # On edit, keep the original author; on create, use the logged-in user.
        self.author = self.instance.author if self.instance.pk else author

    def clean_title(self):
        title = self.cleaned_data["title"].strip()
        if len(title) < 5:
            raise forms.ValidationError("Title must be at least 5 characters.")
        # Django skips the (author, title) constraint check since author isn't a form field.
        duplicates = Article.objects.filter(author=self.author, title__iexact=title)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if self.author is not None and duplicates.exists():
            raise forms.ValidationError("You already published an article with this title.")
        return title

    def clean_summary(self):
        return self.cleaned_data["summary"].strip()

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 50:
            raise forms.ValidationError("Article must be at least 50 characters.")
        return content


class CommentForm(forms.ModelForm):

    class Meta:
        model = Comment
        fields = ["content"]
        labels = {"content": "Your comment"}
        widgets = {
            "content": forms.Textarea(
                attrs={"rows": 3, "maxlength": 1000, "placeholder": "Share a tip or ask a question"}
            ),
        }

    def clean_content(self):
        content = self.cleaned_data["content"].strip()
        if len(content) < 2:
            raise forms.ValidationError("Comment is too short.")
        if len(content) > 1000:
            raise forms.ValidationError("Comment must be 1000 characters or fewer.")
        return content


class ArticleFilterForm(forms.Form):
    """Search and category filter. Both optional; empty means 'any'."""

    q = forms.CharField(
        required=False,
        max_length=100,
        label="Search articles",
        widget=forms.TextInput(attrs={"placeholder": "Search articles", "type": "search"}),
    )
    category = forms.ChoiceField(
        required=False,
        choices=[("", "All topics")] + list(Article.Category.choices),
    )
