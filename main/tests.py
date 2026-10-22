from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import WasteReport

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
