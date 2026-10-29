from django.urls import path

from educational_hub.views import (
    article_list,
    saved_articles,
    article_create,
    article_detail,
    article_update,
    article_delete,
    toggle_like,
    toggle_favorite,
    comment_create,
)

# The shared navbar highlights "Learn" when the namespace is 'education'.
app_name = 'education'

urlpatterns = [
    path('', article_list, name='article_list'),
    path('saved/', saved_articles, name='saved_articles'),
    path('new/', article_create, name='article_create'),
    path('<int:pk>/', article_detail, name='article_detail'),
    path('<int:pk>/edit/', article_update, name='article_update'),
    path('<int:pk>/delete/', article_delete, name='article_delete'),
    path('<int:pk>/like/', toggle_like, name='toggle_like'),
    path('<int:pk>/favorite/', toggle_favorite, name='toggle_favorite'),
    path('<int:pk>/comments/', comment_create, name='comment_create'),
]
