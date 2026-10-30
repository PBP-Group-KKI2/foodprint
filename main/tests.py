import re

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Profile, WasteReport

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class ReportingTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.bob = User.objects.create_user("bob", password="pass12345")
        self.report = WasteReport.objects.create(
            reporter=self.alice,
            title="Rice behind canteen",
            waste_type=WasteReport.WasteType.FOOD,
            severity=WasteReport.Severity.HIGH,
            latitude=-6.3628,
            longitude=106.8269,
        )
        self.valid = {
            "title": "Bread near station",
            "description": "Two bags",
            "waste_type": "FOOD",
            "severity": "LOW",
            "location_name": "Stasiun UI",
            "latitude": "-6.360912345678",
            "longitude": "106.831234567",
        }

    # ---------- pages ----------

    def test_map_page_renders_for_anonymous(self):
        res = self.client.get(reverse("main:report_map"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Rice behind canteen")
        self.assertContains(res, "Log in")
        self.assertNotContains(res, 'id="rp-form"')

    def test_map_page_shows_form_when_logged_in(self):
        self.client.login(username="bob", password="pass12345")
        res = self.client.get(reverse("main:report_map"))
        self.assertContains(res, 'id="rp-form"')

    def test_detail_page(self):
        res = self.client.get(reverse("main:report_detail", args=[self.report.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Rice behind canteen")

    # ---------- AJAX create ----------

    def test_create_requires_login(self):
        res = self.client.post(reverse("main:report_create"), self.valid, **AJAX)
        self.assertEqual(res.status_code, 401)
        self.assertEqual(WasteReport.objects.count(), 1)

    def test_create_valid(self):
        self.client.login(username="bob", password="pass12345")
        res = self.client.post(reverse("main:report_create"), self.valid, **AJAX)
        self.assertEqual(res.status_code, 201)
        report = WasteReport.objects.get(pk=res.json()["report"]["id"])
        self.assertEqual(report.reporter, self.bob)
        self.assertEqual(report.status, WasteReport.Status.REPORTED)
        self.assertEqual(report.latitude, -6.360912)  # rounded to 6 dp

    def test_create_without_location_returns_errors(self):
        self.client.login(username="bob", password="pass12345")
        data = {**self.valid, "latitude": "", "longitude": ""}
        res = self.client.post(reverse("main:report_create"), data, **AJAX)
        self.assertEqual(res.status_code, 400)
        self.assertIn("latitude", res.json()["errors"])

    def test_create_rejects_out_of_range_coordinates(self):
        self.client.login(username="bob", password="pass12345")
        data = {**self.valid, "latitude": "123"}
        res = self.client.post(reverse("main:report_create"), data, **AJAX)
        self.assertEqual(res.status_code, 400)

    # ---------- filtering ----------

    def test_json_filters(self):
        WasteReport.objects.create(
            reporter=self.bob, title="Packaging pile", waste_type="PACKAGING",
            severity="LOW", latitude=-6.36, longitude=106.82,
        )
        url = reverse("main:report_list_json")
        self.assertEqual(self.client.get(url).json()["count"], 2)
        self.assertEqual(self.client.get(url, {"waste_type": "PACKAGING"}).json()["count"], 1)
        self.assertEqual(self.client.get(url, {"severity": "HIGH"}).json()["count"], 1)
        self.assertEqual(self.client.get(url, {"q": "canteen"}).json()["count"], 1)

    def test_mine_filter_only_applies_when_logged_in(self):
        WasteReport.objects.create(
            reporter=self.bob, title="Bob's report", latitude=-6.36, longitude=106.82,
        )
        url = reverse("main:report_list_json")
        self.assertEqual(self.client.get(url, {"mine": "on"}).json()["count"], 2)
        self.client.login(username="bob", password="pass12345")
        data = self.client.get(url, {"mine": "on"}).json()
        self.assertEqual(data["count"], 1)
        self.assertTrue(data["reports"][0]["is_owner"])

    def test_json_escapes_html_in_list(self):
        WasteReport.objects.create(
            reporter=self.bob, title="<script>x</script>", latitude=0, longitude=0,
        )
        html = self.client.get(reverse("main:report_list_json")).json()["html"]
        self.assertNotIn("<script>x</script>", html)

    # ---------- owner-only edit/delete ----------

    def test_update_by_owner(self):
        self.client.login(username="alice", password="pass12345")
        data = {**self.valid, "title": "Updated title"}
        res = self.client.post(reverse("main:report_update", args=[self.report.pk]), data)
        self.assertRedirects(res, reverse("main:report_detail", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, "Updated title")

    def test_update_by_other_user_forbidden(self):
        self.client.login(username="bob", password="pass12345")
        res = self.client.get(reverse("main:report_update", args=[self.report.pk]))
        self.assertEqual(res.status_code, 403)

    def test_update_anonymous_redirects_to_login(self):
        res = self.client.get(reverse("main:report_update", args=[self.report.pk]))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("main:login"), res["Location"])

    def test_delete_by_other_user_forbidden(self):
        self.client.login(username="bob", password="pass12345")
        res = self.client.post(reverse("main:report_delete", args=[self.report.pk]), **AJAX)
        self.assertEqual(res.status_code, 403)
        self.assertTrue(WasteReport.objects.filter(pk=self.report.pk).exists())

    def test_delete_by_owner_ajax(self):
        self.client.login(username="alice", password="pass12345")
        res = self.client.post(reverse("main:report_delete", args=[self.report.pk]), **AJAX)
        self.assertEqual(res.json(), {"deleted": self.report.pk})
        self.assertFalse(WasteReport.objects.exists())

    def test_delete_requires_post(self):
        self.client.login(username="alice", password="pass12345")
        res = self.client.get(reverse("main:report_delete", args=[self.report.pk]))
        self.assertEqual(res.status_code, 405)  


class ReportAreaTests(TestCase):
    """City / district (kecamatan) on waste reports."""

    def setUp(self):
        self.user = User.objects.create_user("dina", password="pass12345")
        self.client.login(username="dina", password="pass12345")
        self.data = {
            "title": "Rice near station",
            "waste_type": "FOOD",
            "severity": "HIGH",
            "latitude": "-6.3608",
            "longitude": "106.8312",
            "city": "  Depok ",
            "district": "Beji",
        }

    def test_create_saves_city_and_district(self):
        res = self.client.post(reverse("main:report_create"), self.data, **AJAX)
        self.assertEqual(res.status_code, 201)
        body = res.json()["report"]
        self.assertEqual(body["city"], "Depok")  # whitespace tidied
        self.assertEqual(body["district"], "Beji")
        report = WasteReport.objects.get(pk=body["id"])
        self.assertEqual(report.area_label, "Beji, Depok")

    def test_city_and_district_are_optional(self):
        data = {**self.data, "city": "", "district": ""}
        res = self.client.post(reverse("main:report_create"), data, **AJAX)
        self.assertEqual(res.status_code, 201)

    def test_filter_by_city_and_district(self):
        make = WasteReport.objects.create
        make(reporter=self.user, title="A", latitude=0, longitude=0, city="Depok", district="Beji")
        make(reporter=self.user, title="B", latitude=0, longitude=0, city="Depok", district="Pancoran Mas")
        make(reporter=self.user, title="C", latitude=0, longitude=0, city="Jakarta Selatan", district="Jagakarsa")
        url = reverse("main:report_list_json")
        self.assertEqual(self.client.get(url, {"city": "Depok"}).json()["count"], 2)
        self.assertEqual(self.client.get(url, {"district": "Jagakarsa"}).json()["count"], 1)
        self.assertEqual(self.client.get(url, {"q": "pancoran"}).json()["count"], 1)

    def test_filter_dropdown_lists_existing_cities(self):
        WasteReport.objects.create(reporter=self.user, title="A", latitude=0, longitude=0, city="Depok")
        res = self.client.get(reverse("main:report_map"))
        self.assertContains(res, '<option value="Depok">Depok</option>', html=True)



class ReportAdminPermissionTests(TestCase):
    """Admins (staff) can edit, delete and resolve any report; others still can't."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass12345")
        self.admin = User.objects.create_user("boss", password="pass12345", is_staff=True)
        self.other = User.objects.create_user("other", password="pass12345")
        self.report = WasteReport.objects.create(
            reporter=self.owner, title="Rice behind canteen", latitude=-6.36, longitude=106.82,
        )
        self.edit_url = reverse("main:report_update", args=[self.report.pk])
        self.delete_url = reverse("main:report_delete", args=[self.report.pk])
        self.edit_data = {
            "title": "Rice behind canteen",
            "waste_type": "FOOD",
            "severity": "HIGH",
            "latitude": "-6.36",
            "longitude": "106.82",
        }

    def test_admin_can_delete_any_report(self):
        self.client.login(username="boss", password="pass12345")
        res = self.client.post(self.delete_url, **AJAX)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(WasteReport.objects.filter(pk=self.report.pk).exists())

    def test_admin_can_edit_and_resolve_any_report(self):
        self.client.login(username="boss", password="pass12345")
        res = self.client.post(self.edit_url, {**self.edit_data, "status": "RESOLVED"})
        self.assertRedirects(res, reverse("main:report_detail", args=[self.report.pk]))
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, WasteReport.Status.RESOLVED)

    def test_admin_sees_status_field_owner_does_not(self):
        self.client.login(username="boss", password="pass12345")
        self.assertContains(self.client.get(self.edit_url), 'name="status"')
        self.client.login(username="owner", password="pass12345")
        self.assertNotContains(self.client.get(self.edit_url), 'name="status"')

    def test_owner_cannot_change_status(self):
        self.client.login(username="owner", password="pass12345")
        self.client.post(self.edit_url, {**self.edit_data, "status": "RESOLVED"})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, WasteReport.Status.REPORTED)

    def test_other_user_still_blocked(self):
        self.client.login(username="other", password="pass12345")
        self.assertEqual(self.client.get(self.edit_url).status_code, 403)
        self.assertEqual(self.client.post(self.delete_url, **AJAX).status_code, 403)

    def test_admin_sees_edit_and_delete_buttons(self):
        self.client.login(username="boss", password="pass12345")
        detail = self.client.get(reverse("main:report_detail", args=[self.report.pk]))
        self.assertContains(detail, self.edit_url)
        html = self.client.get(reverse("main:report_list_json")).json()["html"]
        self.assertIn("data-delete-url", html)

class NavbarActiveStateTests(TestCase):
    """The navbar highlights the section the current page belongs to."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")
        Profile.objects.create(user=self.user, role="USERS")
        self.client.login(username="alice", password="pass12345")

    def active_link(self, url, label):
        return f'<a href="{url}" class="navbar__link navbar__link--active" aria-current="page">{label}</a>'

    def test_rewards_link_is_active_on_rewards_page(self):
        res = self.client.get(reverse("main:show_reward"))
        self.assertContains(res, self.active_link(reverse("main:show_reward"), "Rewards"), html=True)

    def test_only_one_item_is_active(self):
        res = self.client.get(reverse("main:show_reward"))
        html = res.content.decode()
        self.assertEqual(html.count("navbar__link--active"), 1)
        # one aria-current in the desktop nav, one in the mobile menu
        self.assertEqual(html.count('aria-current="page"'), 2)

    def test_report_detail_keeps_reporting_active(self):
        report = WasteReport.objects.create(reporter=self.user, title="Rice", latitude=0, longitude=0)
        res = self.client.get(reverse("main:report_detail", args=[report.pk]))
        self.assertContains(
            res, self.active_link(reverse("main:report_map"), "Reporting &amp; Mapping"), html=True
        )


class DashboardNavigationTests(TestCase):
    """The Dashboard link goes through dashboard_router to each role's own page."""

    def setUp(self):
        for username, role in [("citizen", "USERS"), ("official", "OFFICIAL"), ("org", "ORGANIZATION")]:
            user = User.objects.create_user(username, password="pass12345")
            Profile.objects.create(user=user, role=role)

    def test_navbar_dashboard_link_points_to_router(self):
        self.client.login(username="citizen", password="pass12345")
        res = self.client.get(reverse("main:report_map"))
        self.assertContains(res, f'href="{reverse("main:dashboard_router")}"', count=2)  # desktop + mobile

    def test_anonymous_is_sent_to_login(self):
        res = self.client.get(reverse("main:dashboard_router"))
        self.assertRedirects(
            res, f'{reverse("main:login")}?next={reverse("main:dashboard_router")}',
        )

    def test_each_role_reaches_its_own_dashboard(self):
        expected = {
            "citizen": "main:users_dashboard",
            "official": "main:official_dashboard",
            "org": "main:organization_dashboard",
        }
        for username, url_name in expected.items():
            with self.subTest(username=username):
                self.client.login(username=username, password="pass12345")
                res = self.client.get(reverse("main:dashboard_router"), follow=True)
                self.assertRedirects(res, reverse(url_name))
                self.assertEqual(res.status_code, 200)

    def test_dashboard_link_is_active_on_dashboard(self):
        self.client.login(username="citizen", password="pass12345")
        res = self.client.get(reverse("main:users_dashboard"))
        self.assertContains(
            res,
            f'<a href="{reverse("main:dashboard_router")}" class="navbar__link navbar__link--active" aria-current="page">Dashboard</a>',
            html=True,
        )

    def test_analytics_page_does_not_mark_dashboard_active(self):
        self.client.login(username="org", password="pass12345")
        html = self.client.get(reverse("analytics:show_analytics")).content.decode()
        self.assertEqual(html.count("navbar__link--active"), 1)

    def test_landing_page_links(self):
        self.client.login(username="citizen", password="pass12345")
        res = self.client.get(reverse("main:landing"))
        self.assertContains(res, f'<a href="{reverse("main:show_reward")}" class="navbar__link">Rewards</a>', html=True)
        self.assertContains(res, f'<li><a href="{reverse("main:dashboard_router")}">Dashboard</a></li>', html=True)


class OrganizationDashboardTests(TestCase):
    def test_data_insights_button_opens_analytics(self):
        user = User.objects.create_user("org", password="pass12345")
        Profile.objects.create(user=user, role="ORGANIZATION")
        self.client.login(username="org", password="pass12345")
        res = self.client.get(reverse("main:organization_dashboard"))
        self.assertContains(
            res,
            f'<a href="{reverse("analytics:show_analytics")}" class="dashboard-btn dashboard-btn--outline">View Data Insights</a>',
            html=True,
        )


class PlaceholderLinkTests(TestCase):
    """No link on the shared layout or landing page should still point to "#"."""

    def setUp(self):
        user = User.objects.create_user("alice", password="pass12345")
        Profile.objects.create(user=user, role="USERS")

    def test_no_placeholder_links(self):
        for logged_in in (False, True):
            if logged_in:
                self.client.login(username="alice", password="pass12345")
            for url_name in ("main:landing", "main:report_map"):
                with self.subTest(page=url_name, logged_in=logged_in):
                    self.assertNotContains(self.client.get(reverse(url_name)), 'href="#"')

    def test_landing_feature_cards_link_to_modules(self):
        res = self.client.get(reverse("main:landing"))
        for url_name in ("main:report_map", "main:show_reward", "main:dashboard_router"):
            self.assertContains(res, f'<a href="{reverse(url_name)}" class="feature-card">')
        self.assertNotContains(res, "Coming soon")


class MissingProfileTests(TestCase):
    """Accounts made with createsuperuser have no Profile and must not crash pages."""

    def setUp(self):
        self.admin = User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        self.client.login(username="admin", password="pass12345")

    def test_rewards_page_works_without_profile(self):
        res = self.client.get(reverse("main:show_reward"))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Points: <strong>0</strong>", html=True)

    def test_toggle_rank_works_without_profile(self):
        res = self.client.post(reverse("main:toggle_rank"), {"next": reverse("main:landing")})
        self.assertRedirects(res, reverse("main:landing"))
        self.assertFalse(Profile.objects.get(user=self.admin).show_rank)

    def test_role_dashboards_deny_instead_of_crashing(self):
        for url_name in ("main:official_dashboard", "main:organization_dashboard"):
            with self.subTest(url_name=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 403)

    def test_dashboard_router_still_reaches_a_dashboard(self):
        res = self.client.get(reverse("main:dashboard_router"), follow=True)
        self.assertRedirects(res, reverse("main:users_dashboard"))

    def test_wrong_role_is_still_forbidden(self):
        citizen = User.objects.create_user("citizen", password="pass12345")
        Profile.objects.create(user=citizen, role="USERS")
        self.client.login(username="citizen", password="pass12345")
        self.assertEqual(self.client.get(reverse("main:official_dashboard")).status_code, 403)


class RewardRankHintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")
        self.profile = Profile.objects.create(user=self.user, role="USERS")
        self.client.login(username="alice", password="pass12345")

    def test_hint_matches_each_rank(self):
        cases = [
            (0, 'Reach 100 points to become "Civic"', "0/100"),
            (150, 'Reach 300 points to become "Critical"', "150/300"),
            (500, 'Reach 1000 points to become "Concise"', "500/1000"),
            (1200, "You are already on maximum level", "1200"),
        ]
        for points, hint, progress in cases:
            with self.subTest(points=points):
                self.profile.points = points
                self.profile.save()
                res = self.client.get(reverse("main:show_reward"))
                self.assertContains(res, hint)
                self.assertContains(res, f'<span class="progress__text">{progress}</span>', html=True)


class UpdateProfileUsernameTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")
        Profile.objects.create(user=self.user, role="USERS", email="alice@example.com")
        User.objects.create_user("bob", password="pass12345")
        self.client.login(username="alice", password="pass12345")
        self.url = reverse("main:update_profile")

    def test_taken_username_shows_error_instead_of_crashing(self):
        res = self.client.post(self.url, {"username": "bob", "email": "alice@example.com"})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "That username is already taken.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "alice")

    def test_free_username_is_saved(self):
        res = self.client.post(self.url, {"username": "alicia", "email": "alice@example.com"})
        self.assertRedirects(res, reverse("main:dashboard_router"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "alicia")


class RegisterRoleTests(TestCase):
    """Every role can sign up; admins can still change a role later in /admin/."""

    def data(self, role):
        return {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "Xq-secret-9876",
            "password2": "Xq-secret-9876",
            "role": role,
        }

    def test_every_role_is_offered(self):
        res = self.client.get(reverse("main:register"))
        for role in ("USERS", "ORGANIZATION", "OFFICIAL"):
            self.assertContains(res, f'value="{role}"')

    def test_each_role_can_register(self):
        for role in ("USERS", "ORGANIZATION", "OFFICIAL"):
            with self.subTest(role=role):
                User.objects.filter(username="newuser").delete()
                res = self.client.post(reverse("main:register"), self.data(role))
                self.assertRedirects(res, reverse("main:dashboard_router"), fetch_redirect_response=False)
                self.assertEqual(Profile.objects.get(user__username="newuser").role, role)
                self.client.logout()

    def test_admin_can_promote_a_user_to_official(self):
        User.objects.create_superuser("admin", "admin@example.com", "pass12345")
        user = User.objects.create_user("newuser", password="pass12345")
        profile = Profile.objects.create(user=user, role="USERS")
        self.client.login(username="admin", password="pass12345")
        res = self.client.post(
            reverse("admin:main_profile_change", args=[profile.pk]),
            {"user": user.pk, "role": "OFFICIAL", "email": "", "points": 0, "show_rank": "on"},
        )
        self.assertRedirects(res, reverse("admin:main_profile_changelist"))
        profile.refresh_from_db()
        self.assertEqual(profile.role, "OFFICIAL")


class SharedNavbarTests(TestCase):
    """Every page, including the landing page, renders the same shared navbar."""

    def setUp(self):
        self.official = User.objects.create_user("officer", password="pass12345")
        Profile.objects.create(user=self.official, role="OFFICIAL")
        self.citizen = User.objects.create_user("citizen", password="pass12345")
        Profile.objects.create(user=self.citizen, role="USERS")

    def navbar(self, url):
        html = self.client.get(url).content.decode()
        self.assertEqual(html.count('<header class="navbar">'), 1)
        block = re.search(r'<header class="navbar">.*?</header>', html, re.S).group(0)
        # Ignore the parts that legitimately change per page
        block = re.sub(r' navbar__link--active| aria-current="page"|name="next" value="[^"]*"', "", block)
        return re.sub(r'name="csrfmiddlewaretoken" value="[^"]*"', "", block)

    def test_landing_page_uses_the_shared_navbar(self):
        for user in (None, self.citizen, self.official):
            with self.subTest(user=user):
                if user:
                    self.client.force_login(user)
                self.assertEqual(self.navbar(reverse("main:landing")), self.navbar(reverse("main:report_map")))

    def test_landing_page_marks_home_active(self):
        res = self.client.get(reverse("main:landing"))
        self.assertContains(
            res, f'<a href="{reverse("main:landing")}" class="navbar__link navbar__link--active" aria-current="page">Home</a>', html=True,
        )

    def test_account_controls_are_grouped_in_one_menu(self):
        self.client.force_login(self.official)
        res = self.client.get(reverse("main:report_map"))
        menu = re.search(r'<details class="navbar__account">.*?</details>', res.content.decode(), re.S).group(0)
        self.assertIn(f'href="{reverse("main:update_profile")}"', menu)
        self.assertIn(f'action="{reverse("main:toggle_rank")}"', menu)
        self.assertIn(f'href="{reverse("main:logout")}"', menu)
        self.assertNotContains(res, "navbar__cta")

    def test_role_specific_links(self):
        tasks, analytics = reverse("dispatch:pending_reports"), reverse("analytics:show_analytics")
        self.client.force_login(self.official)
        res = self.client.get(reverse("main:report_map"))
        self.assertContains(res, f'<a href="{tasks}" class="navbar__link">Tasks</a>', html=True)
        self.assertContains(res, f'<a href="{analytics}" class="navbar__link">Analytics</a>', html=True)
        self.client.force_login(self.citizen)
        res = self.client.get(reverse("main:report_map"))
        self.assertNotContains(res, ">Tasks</a>")
        self.assertNotContains(res, ">Analytics</a>")

    def test_anonymous_sees_log_in_instead_of_account_menu(self):
        res = self.client.get(reverse("main:report_map"))
        self.assertContains(res, f'<a href="{reverse("main:login")}" class="btn btn--outline navbar__cta">Log in</a>', html=True)
        self.assertNotContains(res, '<details class="navbar__account">')


class LandingPageContentTests(TestCase):
    """The landing page shows real data and only links to pages that exist."""

    def setUp(self):
        self.user = User.objects.create_user("alice", password="pass12345")
        Profile.objects.create(user=self.user, role="USERS")

    def test_report_counts_come_from_the_database(self):
        for status in ("REPORTED", "REPORTED", "RESOLVED"):
            WasteReport.objects.create(reporter=self.user, title="Rice", latitude=0, longitude=0, status=status)
        res = self.client.get(reverse("main:landing"))
        self.assertContains(res, '<span class="card__number">3</span>', html=True)
        self.assertContains(res, "1 resolved")

    def test_latest_articles_are_listed(self):
        from educational_hub.models import Article
        titles = ["First guide", "Second guide", "Third guide", "Fourth guide"]
        for title in titles:
            Article.objects.create(author=self.user, title=title, content="x" * 60)
        res = self.client.get(reverse("main:landing"))
        for article in Article.objects.filter(title__in=titles[1:]):
            self.assertContains(res, f'href="{article.get_absolute_url()}"')
        self.assertNotContains(res, "First guide")

    def test_empty_learn_section_invites_a_first_article(self):
        res = self.client.get(reverse("main:landing"))
        self.assertContains(res, f'href="{reverse("education:article_create")}"')

    def test_hero_offers_report_and_learn_actions(self):
        res = self.client.get(reverse("main:landing"))
        self.assertContains(res, f'href="{reverse("main:report_map")}#rp-form-card" class="btn btn--light"')
        self.assertContains(res, f'href="{reverse("education:article_list")}" class="btn btn--outline"')

    def test_task_dispatch_card_links_only_for_officials(self):
        card_link = f'<a href="{reverse("dispatch:pending_reports")}" class="feature-card">'
        self.assertNotContains(self.client.get(reverse("main:landing")), card_link)
        official = User.objects.create_user("officer", password="pass12345")
        Profile.objects.create(user=official, role="OFFICIAL")
        self.client.force_login(official)
        self.assertContains(self.client.get(reverse("main:landing")), card_link)

    def test_every_internal_link_resolves(self):
        from django.urls import resolve
        html = self.client.get(reverse("main:landing")).content.decode()
        paths = {href.split("#")[0].split("?")[0] for href in re.findall(r'href="(/[^"]*)"', html)}
        for path in paths - {""}:
            if not path.startswith("/static/"):
                with self.subTest(path=path):
                    resolve(path)
