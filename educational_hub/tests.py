from unittest import mock
from urllib.error import URLError

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from main.models import Profile

from .food_waste_data import FRESH_KEY, get_food_waste_data
from .views import ARTICLE_RATE_LIMIT, LIKE_RATE_LIMIT
from .models import Article, Comment, Favorite, Like

HTMX = {"HTTP_HX_REQUEST": "true"}
LONG_TEXT = "Food scraps like peels and coffee grounds can be composted at home. " * 2


class EducationalHubTests(TestCase):
    def setUp(self):
        cache.clear()  # reset the comment cooldown between tests
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.staff = User.objects.create_user("staff", password="pass12345", is_staff=True)
        Profile.objects.create(user=self.alice, role="ORGANIZATION", email="alice@example.com")
        self.article = Article.objects.create(
            author=self.alice,
            title="Composting basics",
            category=Article.Category.COMPOSTING,
            content=LONG_TEXT,
        )
        self.valid = {
            "title": "Sorting at the canteen",
            "category": "SORTING",
            "summary": "",
            "content": LONG_TEXT,
        }

    def login(self, user):
        self.client.login(username=user.username, password="pass12345")

    def url(self, name, article=None):
        return reverse(f"education:{name}", args=[(article or self.article).pk])

    # ---------- reading (everyone) ----------

    def test_anonymous_can_view_list_and_detail(self):
        res = self.client.get(reverse("education:article_list"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Composting basics")
        self.assertContains(res, "Organization")  # author's profile role badge
        self.assertContains(res, "Log in to write")
        self.assertNotContains(res, reverse("education:article_create"))

        res = self.client.get(self.url("article_detail"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Log in to like or save")
        self.assertNotContains(res, self.url("article_update"))
        self.assertNotContains(res, 'name="content"')  # no comment form

    def test_empty_state(self):
        Article.objects.all().delete()
        res = self.client.get(reverse("education:article_list"))
        self.assertContains(res, "No articles yet")

    def test_search_and_category_filter(self):
        Article.objects.create(author=self.bob, title="Plastic-free shopping", category="REDUCING", content=LONG_TEXT)
        url = reverse("education:article_list")
        res = self.client.get(url, {"q": "plastic"})
        self.assertContains(res, "Plastic-free shopping")
        self.assertNotContains(res, "Composting basics")
        res = self.client.get(url, {"category": "COMPOSTING"})
        self.assertContains(res, "Composting basics")
        self.assertNotContains(res, "Plastic-free shopping")
        res = self.client.get(url, {"q": "nothing-matches-this"})
        self.assertContains(res, "No articles match your search")

    def test_htmx_search_returns_partial(self):
        res = self.client.get(reverse("education:article_list"), {"q": "compost"}, **HTMX)
        self.assertContains(res, "Composting basics")
        self.assertNotContains(res, "<html")
        self.assertIn("HX-Request", res["Vary"])

    def test_pagination(self):
        for i in range(10):
            Article.objects.create(author=self.bob, title=f"Article number {i}", content=LONG_TEXT)
        url = reverse("education:article_list")
        self.assertEqual(len(self.client.get(url).context["page_obj"]), 9)
        res = self.client.get(url, {"page": 2})
        self.assertEqual(len(res.context["page_obj"]), 2)
        self.assertContains(res, "Page 2 of 2")

    def test_list_is_newest_first_with_few_queries(self):
        newer = Article.objects.create(author=self.bob, title="Newer article", content=LONG_TEXT)
        self.login(self.bob)
        res = self.client.get(reverse("education:article_list"))
        self.assertEqual(list(res.context["page_obj"]), [newer, self.article])
        # Session + user + count + one page query, no matter how many articles.
        with self.assertNumQueries(5):
            self.client.get(reverse("education:article_list"))

    def test_user_content_is_escaped(self):
        Article.objects.create(author=self.bob, title="<script>alert(1)</script>", content=LONG_TEXT + "<b>x</b>")
        res = self.client.get(reverse("education:article_list"))
        self.assertNotContains(res, "<script>alert(1)</script>")
        self.assertContains(res, "&lt;script&gt;")

    # ---------- create ----------

    def test_create_requires_login(self):
        res = self.client.get(reverse("education:article_create"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("main:login"), res["Location"])
        self.client.post(reverse("education:article_create"), self.valid)
        self.assertEqual(Article.objects.count(), 1)

    def test_create_sets_author_from_session(self):
        self.login(self.bob)
        # Trying to post as Alice is ignored: the form has no author field.
        res = self.client.post(reverse("education:article_create"), {**self.valid, "author": self.alice.pk})
        article = Article.objects.get(title="Sorting at the canteen")
        self.assertRedirects(res, article.get_absolute_url())
        self.assertEqual(article.author, self.bob)

    def test_create_invalid_keeps_input_and_shows_errors(self):
        self.login(self.bob)
        res = self.client.post(reverse("education:article_create"), {**self.valid, "content": "too short"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "at least 50 characters")
        self.assertContains(res, 'value="Sorting at the canteen"')
        self.assertEqual(Article.objects.count(), 1)

    def test_create_duplicate_title_rejected(self):
        self.login(self.alice)
        res = self.client.post(reverse("education:article_create"), {**self.valid, "title": "composting BASICS"})
        self.assertContains(res, "already published an article with this title")
        self.assertEqual(Article.objects.count(), 1)

    # ---------- edit ----------

    def test_owner_can_edit_and_keeps_ownership(self):
        self.login(self.alice)
        res = self.client.post(self.url("article_update"), {**self.valid, "title": "Composting 101"})
        self.assertRedirects(res, self.article.get_absolute_url())
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Composting 101")
        self.assertEqual(self.article.author, self.alice)

    def test_other_user_cannot_edit(self):
        self.login(self.bob)
        self.assertEqual(self.client.get(self.url("article_update")).status_code, 403)
        res = self.client.post(self.url("article_update"), {**self.valid, "title": "Hacked"})
        self.assertEqual(res.status_code, 403)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Composting basics")

    def test_detail_hides_manage_buttons_for_other_user(self):
        self.login(self.bob)
        res = self.client.get(self.url("article_detail"))
        self.assertNotContains(res, self.url("article_update"))
        self.assertNotContains(res, self.url("article_delete"))

    def test_staff_can_edit_without_taking_ownership(self):
        self.login(self.staff)
        self.assertContains(self.client.get(self.url("article_detail")), self.url("article_update"))
        self.client.post(self.url("article_update"), {**self.valid, "title": "Edited by staff"})
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, "Edited by staff")
        self.assertEqual(self.article.author, self.alice)

    def test_edit_anonymous_redirects_to_login(self):
        res = self.client.get(self.url("article_update"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("main:login"), res["Location"])

    # ---------- delete ----------

    def test_delete_modal_only_for_owner(self):
        self.login(self.alice)
        res = self.client.get(self.url("article_detail"))
        self.assertContains(res, 'id="educational-hub-delete-dialog"')
        self.assertContains(res, f'action="{self.url("article_delete")}"')
        self.login(self.bob)
        self.assertNotContains(self.client.get(self.url("article_detail")), "educational-hub-delete-dialog")

    def test_delete_get_only_shows_confirmation(self):
        self.login(self.alice)
        res = self.client.get(self.url("article_delete"))
        self.assertContains(res, "Delete this article?")
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_owner_delete_cascades_related_rows(self):
        Like.objects.create(article=self.article, user=self.bob)
        Favorite.objects.create(article=self.article, user=self.bob)
        Comment.objects.create(article=self.article, author=self.bob, content="Nice")
        self.login(self.alice)
        res = self.client.post(self.url("article_delete"))
        self.assertRedirects(res, reverse("education:article_list"))
        self.assertFalse(Article.objects.exists())
        self.assertFalse(Like.objects.exists() or Favorite.objects.exists() or Comment.objects.exists())

    def test_other_user_cannot_delete(self):
        self.login(self.bob)
        self.assertEqual(self.client.get(self.url("article_delete")).status_code, 403)
        self.assertEqual(self.client.post(self.url("article_delete")).status_code, 403)
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_staff_can_delete(self):
        self.login(self.staff)
        self.client.post(self.url("article_delete"))
        self.assertFalse(Article.objects.exists())

    # ---------- likes & favorites ----------

    def test_anonymous_cannot_like_favorite_or_comment(self):
        self.client.post(self.url("toggle_like"))
        self.client.post(self.url("toggle_favorite"))
        self.client.post(self.url("comment_create"), {"content": "Hi there"})
        self.assertFalse(Like.objects.exists() or Favorite.objects.exists() or Comment.objects.exists())

    def test_anonymous_htmx_gets_hx_redirect(self):
        res = self.client.post(self.url("toggle_like"), **HTMX)
        self.assertEqual(res.status_code, 401)
        self.assertIn(reverse("main:login"), res["HX-Redirect"])

    def test_like_toggles_and_never_duplicates(self):
        self.login(self.bob)
        self.client.post(self.url("toggle_like"))
        self.assertEqual(Like.objects.filter(article=self.article, user=self.bob).count(), 1)
        self.client.post(self.url("toggle_like"))
        self.assertEqual(Like.objects.count(), 0)

    def test_toggle_requires_post(self):
        self.login(self.bob)
        self.assertEqual(self.client.get(self.url("toggle_like")).status_code, 405)
        self.assertEqual(self.client.get(self.url("toggle_favorite")).status_code, 405)

    def test_database_blocks_duplicate_like_and_favorite(self):
        Like.objects.create(article=self.article, user=self.bob)
        Favorite.objects.create(article=self.article, user=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Like.objects.create(article=self.article, user=self.bob)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favorite.objects.create(article=self.article, user=self.bob)

    def test_like_htmx_returns_partial_with_real_count(self):
        Like.objects.create(article=self.article, user=self.alice)
        self.login(self.bob)
        res = self.client.post(self.url("toggle_like"), **HTMX)
        self.assertContains(res, 'aria-pressed="true"')
        self.assertContains(res, "(2 likes)")
        self.assertNotContains(res, "<html")

    def test_like_and_favorite_are_independent(self):
        self.login(self.bob)
        self.client.post(self.url("toggle_favorite"))
        self.assertEqual(Favorite.objects.count(), 1)
        self.assertEqual(Like.objects.count(), 0)

    def test_saved_page_shows_only_my_favorites(self):
        other = Article.objects.create(author=self.alice, title="Not saved by bob", content=LONG_TEXT)
        Favorite.objects.create(article=other, user=self.alice)
        Favorite.objects.create(article=self.article, user=self.bob)
        self.login(self.bob)
        res = self.client.get(reverse("education:saved_articles"))
        self.assertContains(res, "Composting basics")
        self.assertNotContains(res, "Not saved by bob")

    def test_saved_page_requires_login(self):
        res = self.client.get(reverse("education:saved_articles"))
        self.assertEqual(res.status_code, 302)

    # ---------- comments ----------

    def test_comment_saved_with_correct_author_and_article(self):
        self.login(self.bob)
        res = self.client.post(self.url("comment_create"), {"content": "  Great tips!  ", "author": self.alice.pk})
        self.assertRedirects(res, self.article.get_absolute_url() + "#comments")
        comment = Comment.objects.get()
        self.assertEqual((comment.author, comment.article, comment.content), (self.bob, self.article, "Great tips!"))

    def test_invalid_comment_not_saved(self):
        self.login(self.bob)
        res = self.client.post(self.url("comment_create"), {"content": "   "}, **HTMX)
        self.assertContains(res, "This field is required")
        self.assertFalse(Comment.objects.exists())

    def test_comment_htmx_returns_section(self):
        self.login(self.bob)
        res = self.client.post(self.url("comment_create"), {"content": "<script>x</script>"}, **HTMX)
        self.assertContains(res, 'id="comments"')
        self.assertContains(res, "Comment posted.")
        self.assertContains(res, "&lt;script&gt;x&lt;/script&gt;")
        self.assertNotContains(res, "<script>x</script>")

    def test_comment_throttle_and_duplicate(self):
        self.login(self.bob)
        self.client.post(self.url("comment_create"), {"content": "First"})
        res = self.client.post(self.url("comment_create"), {"content": "First"}, **HTMX)
        self.assertContains(res, "You just posted this comment")
        res = self.client.post(self.url("comment_create"), {"content": "Second"}, **HTMX)
        self.assertContains(res, "Please wait")
        self.assertEqual(Comment.objects.count(), 1)

    # ---------- integration with the rest of FoodPrint ----------

    def test_learn_links_resolve_on_shared_pages(self):
        hub_url = reverse("education:article_list")
        self.assertContains(self.client.get(reverse("main:landing")), f'href="{hub_url}"')
        self.assertContains(self.client.get(reverse("main:report_map")), f'href="{hub_url}"')

    def test_navbar_marks_learn_active_on_hub(self):
        res = self.client.get(reverse("education:article_list"))
        self.assertContains(res, f'href="{reverse("education:article_list")}" class="navbar__link navbar__link--active"')


# ---------- global food waste data (public API) ----------

SAMPLE_CSV = (
    "entity,code,year,_12_3_1__ag_food_wst_pc__retail,"
    "_12_3_1__ag_food_wst_pc__out_of_home_consumption,_12_3_1__ag_food_wst_pc__households\n"
    "Indonesia,IDN,2019,15.7,27.76,77.67\n"
    "Indonesia,IDN,2022,49.93,40.11,53.46\n"
    "Brazil,BRA,2022,10,20,94\n"
    "World,OWID_WRL,2022,16.45,36.34,79.12\n"
    "Asia (UN),UN_ASI,2022,14,30,\n"
)


class FakeResponse:
    def __init__(self, body):
        self.body = body.encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FoodWasteDataTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("education:food_waste_data")

    def fetch(self, body=SAMPLE_CSV):
        return mock.patch("educational_hub.food_waste_data.urlopen", return_value=FakeResponse(body))

    def test_rows_are_parsed(self):
        with self.fetch():
            data = get_food_waste_data()
        self.assertTrue(data.available)
        self.assertFalse(data.stale)
        brazil = next(r for r in data.rows if r.entity == "Brazil")
        self.assertEqual((brazil.year, brazil.households, brazil.total), (2022, 94.0, 124.0))
        self.assertFalse(brazil.is_region)
        asia = next(r for r in data.rows if r.entity == "Asia (UN)")
        self.assertTrue(asia.is_region)
        self.assertIsNone(asia.households)
        self.assertIsNone(asia.total)

    def test_second_call_uses_the_cache(self):
        with self.fetch() as urlopen:
            get_food_waste_data()
            get_food_waste_data()
        self.assertEqual(urlopen.call_count, 1)

    def test_outage_falls_back_to_last_good_copy(self):
        with self.fetch():
            get_food_waste_data()
        cache.delete(FRESH_KEY)
        with mock.patch("educational_hub.food_waste_data.urlopen", side_effect=URLError("down")):
            data = get_food_waste_data()
        self.assertTrue(data.available)
        self.assertTrue(data.stale)

    def test_outage_without_copy_shows_friendly_message(self):
        with mock.patch("educational_hub.food_waste_data.urlopen", side_effect=URLError("down")):
            res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "The data source is unavailable right now")

    def test_malformed_response_is_treated_as_an_outage(self):
        with self.fetch("not,a,dataset\n1,2,3\n"):
            res = self.client.get(self.url)
        self.assertContains(res, "The data source is unavailable right now")

    def test_page_defaults_to_latest_year_countries_sorted_by_total(self):
        with self.fetch():
            res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual([r.entity for r in res.context["rows"]], ["Indonesia", "Brazil"])
        self.assertContains(res, "Our World in Data")

    def test_filters(self):
        cases = [
            ({"q": "bra"}, ["Brazil"]),
            ({"year": "2019"}, ["Indonesia"]),
            ({"scope": "regions"}, ["World", "Asia (UN)"]),
            ({"sort": "households"}, ["Brazil", "Indonesia"]),
        ]
        for params, expected in cases:
            with self.subTest(params=params), self.fetch():
                res = self.client.get(self.url, params)
                self.assertEqual([r.entity for r in res.context["rows"]], expected)

    def test_invalid_filters_fall_back_to_defaults(self):
        with self.fetch():
            res = self.client.get(self.url, {"year": "1800", "sort": "evil", "scope": "x"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual([r.entity for r in res.context["rows"]], ["Indonesia", "Brazil"])

    def test_htmx_returns_only_the_results(self):
        with self.fetch():
            res = self.client.get(self.url, {"q": "indo"}, **HTMX)
        self.assertTemplateUsed(res, "educational_hub/_food_waste_results.html")
        self.assertTemplateNotUsed(res, "educational_hub/food_waste_data.html")
        self.assertIn("HX-Request", res["Vary"])


# ---------- security decorators ----------

class SecurityDecoratorTests(TestCase):
    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.staff = User.objects.create_user("staff", password="pass12345", is_staff=True)
        self.article = Article.objects.create(author=self.alice, title="Composting basics", content=LONG_TEXT)
        self.edit_url = reverse("education:article_update", args=[self.article.pk])
        self.delete_url = reverse("education:article_delete", args=[self.article.pk])
        self.like_url = reverse("education:toggle_like", args=[self.article.pk])

    def test_manager_required_allows_owner_and_staff_only(self):
        for user, expected in ((self.alice, 200), (self.staff, 200), (self.bob, 403)):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertEqual(self.client.get(self.edit_url).status_code, expected)
                self.assertEqual(self.client.get(self.delete_url).status_code, expected)

    def test_manager_required_redirects_anonymous_and_404s_missing_articles(self):
        self.assertRedirects(self.client.get(self.edit_url), f"{reverse('main:login')}?next={self.edit_url}")
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(reverse("education:article_update", args=[9999])).status_code, 404)

    def test_likes_are_rate_limited_per_user(self):
        limit, _ = LIKE_RATE_LIMIT
        self.client.force_login(self.bob)
        for _ in range(limit):
            self.assertEqual(self.client.post(self.like_url, **HTMX).status_code, 200)
        res = self.client.post(self.like_url, **HTMX)
        self.assertEqual(res.status_code, 429)
        self.assertIn("too many", res.content.decode().lower())

        self.client.force_login(self.alice)
        self.assertEqual(self.client.post(self.like_url, **HTMX).status_code, 200)

    def test_article_creation_is_rate_limited_without_htmx(self):
        limit, _ = ARTICLE_RATE_LIMIT
        self.client.force_login(self.bob)
        for i in range(limit):
            self.client.post(reverse("education:article_create"), {
                "title": f"Sorting guide number {i}", "category": "SORTING", "summary": "", "content": LONG_TEXT,
            })
        res = self.client.post(reverse("education:article_create"), {
            "title": "One article too many", "category": "SORTING", "summary": "", "content": LONG_TEXT,
        }, follow=True)
        self.assertFalse(Article.objects.filter(title="One article too many").exists())
        self.assertContains(res, "too many")

    def test_get_requests_are_not_limited(self):
        limit, _ = ARTICLE_RATE_LIMIT
        self.client.force_login(self.bob)
        for _ in range(limit + 3):
            self.assertEqual(self.client.get(reverse("education:article_create")).status_code, 200)

    def test_rate_limit_redirect_ignores_external_referer(self):
        limit, _ = LIKE_RATE_LIMIT
        self.client.force_login(self.bob)
        for _ in range(limit):
            self.client.post(self.like_url)
        res = self.client.post(self.like_url, HTTP_REFERER="https://evil.example/")
        self.assertRedirects(res, reverse("education:article_list"), fetch_redirect_response=False)
