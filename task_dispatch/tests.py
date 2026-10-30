from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from main.models import Profile, WasteReport

from .models import CollectionTask


class TaskDispatchTests(TestCase):
    def setUp(self):
        self.official = self.make_user("officer", "OFFICIAL")
        self.other_official = self.make_user("officer2", "OFFICIAL")
        self.citizen = self.make_user("citizen", "USERS")
        self.report = self.make_report("Rice behind the canteen", severity="HIGH", city="Depok")

    def make_user(self, username, role):
        user = User.objects.create_user(username, password="pass12345")
        Profile.objects.create(user=user, role=role, email=f"{username}@example.com")
        return user

    def make_report(self, title, **kwargs):
        return WasteReport.objects.create(
            reporter=self.citizen, title=title, latitude=-6.36, longitude=106.82, **kwargs
        )

    def login(self, user):
        self.client.login(username=user.username, password="pass12345")

    def claim(self, report=None):
        return self.client.post(reverse("dispatch:claim_report", args=[(report or self.report).pk]))

    def task_url(self, name, task):
        return reverse(f"dispatch:{name}", args=[task.pk])

    # ---------- access ----------

    def test_anonymous_is_sent_to_login(self):
        res = self.client.get(reverse("dispatch:pending_reports"))
        self.assertEqual(res.status_code, 302)
        self.assertIn(reverse("main:login"), res["Location"])

    def test_citizens_are_forbidden(self):
        self.login(self.citizen)
        self.assertEqual(self.client.get(reverse("dispatch:pending_reports")).status_code, 403)
        self.assertEqual(self.claim().status_code, 403)
        self.assertFalse(CollectionTask.objects.exists())

    def test_staff_without_profile_can_dispatch(self):
        User.objects.create_user("admin", password="pass12345", is_staff=True)
        self.client.login(username="admin", password="pass12345")
        self.assertEqual(self.client.get(reverse("dispatch:pending_reports")).status_code, 200)

    def test_official_dashboard_links_to_tasks(self):
        self.login(self.official)
        res = self.client.get(reverse("main:official_dashboard"))
        self.assertContains(res, reverse("dispatch:pending_reports"))
        self.assertContains(res, reverse("dispatch:my_tasks"))

    # ---------- pending list ----------

    def test_pending_list_shows_only_unclaimed_reports(self):
        self.make_report("Already resolved", status=WasteReport.Status.RESOLVED)
        claimed = self.make_report("Claimed by someone")
        CollectionTask.claim(claimed, self.other_official)

        self.login(self.official)
        res = self.client.get(reverse("dispatch:pending_reports"))
        self.assertContains(res, "Rice behind the canteen")
        self.assertNotContains(res, "Already resolved")
        self.assertNotContains(res, "Claimed by someone")

    def test_pending_list_filters_and_sorting(self):
        self.make_report("Old low bins", severity="LOW", city="Jakarta")
        self.login(self.official)
        url = reverse("dispatch:pending_reports")

        res = self.client.get(url, {"city": "Jakarta"})
        self.assertContains(res, "Old low bins")
        self.assertNotContains(res, "Rice behind the canteen")

        res = self.client.get(url, {"q": "canteen"})
        self.assertContains(res, "Rice behind the canteen")
        self.assertNotContains(res, "Old low bins")

        # Default sort puts HIGH before LOW even though the LOW one is newer.
        titles = [r.title for r in self.client.get(url).context["page_obj"]]
        self.assertEqual(titles, ["Rice behind the canteen", "Old low bins"])

        res = self.client.get(url, {"severity": "MEDIUM"})
        self.assertContains(res, "No pending reports match these filters")

    def test_empty_state(self):
        WasteReport.objects.all().delete()
        self.login(self.official)
        self.assertContains(self.client.get(reverse("dispatch:pending_reports")), "No pending reports right now")

    # ---------- claim ----------

    def test_claim_creates_task_and_marks_report_in_progress(self):
        self.login(self.official)
        res = self.claim()
        task = CollectionTask.objects.get()
        self.assertRedirects(res, task.get_absolute_url())
        self.assertEqual(task.official, self.official)
        self.assertEqual(task.status, CollectionTask.Status.CLAIMED)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, WasteReport.Status.IN_PROGRESS)

    def test_report_cannot_be_claimed_twice(self):
        self.login(self.official)
        self.claim()
        self.login(self.other_official)
        res = self.claim()
        self.assertRedirects(res, reverse("dispatch:pending_reports"))
        self.assertEqual(CollectionTask.objects.get().official, self.official)

    def test_claim_requires_post(self):
        self.login(self.official)
        res = self.client.get(reverse("dispatch:claim_report", args=[self.report.pk]))
        self.assertEqual(res.status_code, 405)

    def test_report_detail_shows_claim_button_to_officials(self):
        detail = reverse("main:report_detail", args=[self.report.pk])
        claim_url = reverse("dispatch:claim_report", args=[self.report.pk])

        self.login(self.citizen)
        self.assertNotContains(self.client.get(detail), claim_url)

        self.login(self.official)
        self.assertContains(self.client.get(detail), claim_url)
        self.claim()
        res = self.client.get(detail)
        self.assertNotContains(res, claim_url)
        self.assertContains(res, "claimed by officer")

    # ---------- my tasks, update ----------

    def test_my_tasks_lists_open_and_closed(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.official)
        url = reverse("dispatch:my_tasks")
        self.assertContains(self.client.get(url), "Rice behind the canteen")
        self.assertNotContains(self.client.get(url, {"show": "closed"}), "Rice behind the canteen")

        task.close("Collected two bags.")
        self.assertNotContains(self.client.get(url), "Rice behind the canteen")
        self.assertContains(self.client.get(url, {"show": "closed"}), "Rice behind the canteen")

    def test_update_task(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.official)
        res = self.client.post(self.task_url("task_update", task), {
            "status": "IN_PROGRESS",
            "scheduled_for": "2026-11-02",
            "notes": "Truck B",
        })
        self.assertRedirects(res, task.get_absolute_url())
        task.refresh_from_db()
        self.assertEqual(task.status, CollectionTask.Status.IN_PROGRESS)
        self.assertEqual(task.scheduled_for, date(2026, 11, 2))
        self.assertEqual(task.notes, "Truck B")

    def test_update_cannot_close_task(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.official)
        res = self.client.post(self.task_url("task_update", task), {"status": "CLOSED"})
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, CollectionTask.Status.CLAIMED)

    def test_other_official_cannot_change_task(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.other_official)
        self.assertEqual(self.client.get(self.task_url("task_detail", task)).status_code, 200)
        self.assertEqual(self.client.get(self.task_url("task_update", task)).status_code, 403)
        self.assertEqual(self.client.post(self.task_url("task_close", task), {"closing_note": "Done here"}).status_code, 403)
        self.assertEqual(self.client.post(self.task_url("task_release", task)).status_code, 403)

    # ---------- close, release ----------

    def test_close_task_resolves_report(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.official)
        res = self.client.post(self.task_url("task_close", task), {"closing_note": "Collected 3 bags."})
        self.assertRedirects(res, task.get_absolute_url())
        task.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(task.status, CollectionTask.Status.CLOSED)
        self.assertIsNotNone(task.closed_at)
        self.assertEqual(task.closing_note, "Collected 3 bags.")
        self.assertEqual(self.report.status, WasteReport.Status.RESOLVED)

    def test_close_requires_note(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.official)
        res = self.client.post(self.task_url("task_close", task), {"closing_note": "  "})
        self.assertEqual(res.status_code, 200)
        task.refresh_from_db()
        self.assertTrue(task.is_open)

    def test_closed_task_is_read_only(self):
        task = CollectionTask.claim(self.report, self.official)
        task.close("Collected two bags.")
        self.login(self.official)
        for name in ("task_update", "task_close"):
            self.assertRedirects(self.client.get(self.task_url(name, task)), task.get_absolute_url())
        self.assertRedirects(self.client.post(self.task_url("task_release", task)), task.get_absolute_url())
        self.assertTrue(CollectionTask.objects.filter(pk=task.pk).exists())

    def test_release_returns_report_to_pending(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.official)
        res = self.client.post(self.task_url("task_release", task))
        self.assertRedirects(res, reverse("dispatch:my_tasks"))
        self.assertFalse(CollectionTask.objects.exists())
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, WasteReport.Status.REPORTED)
        self.assertContains(self.client.get(reverse("dispatch:pending_reports")), "Rice behind the canteen")

    # ---------- AJAX claim + navbar ----------

    def ajax_claim(self, report=None):
        return self.client.post(
            reverse("dispatch:claim_report", args=[(report or self.report).pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_ajax_claim_returns_json(self):
        self.make_report("Second pile")
        self.login(self.official)
        res = self.ajax_claim()
        self.assertEqual(res.status_code, 201)
        data = res.json()
        task = CollectionTask.objects.get()
        self.assertEqual(data["claimed"], self.report.pk)
        self.assertEqual(data["task_url"], task.get_absolute_url())
        self.assertEqual(data["pending_count"], 1)
        self.assertEqual(data["open_task_count"], 1)

    def test_ajax_claim_twice_returns_409(self):
        self.login(self.official)
        self.ajax_claim()
        self.login(self.other_official)
        res = self.ajax_claim()
        self.assertEqual(res.status_code, 409)
        self.assertIn("error", res.json())
        self.assertEqual(CollectionTask.objects.get().official, self.official)

    def test_ajax_claim_forbidden_for_citizens(self):
        self.login(self.citizen)
        self.assertEqual(self.ajax_claim().status_code, 403)
        self.assertFalse(CollectionTask.objects.exists())

    def test_navbar_tasks_link_only_for_dispatchers(self):
        tasks_url = reverse("dispatch:pending_reports")
        self.login(self.official)
        self.assertContains(self.client.get(reverse("main:landing")), f'href="{tasks_url}"')
        self.login(self.citizen)
        res = self.client.get(reverse("main:report_map"))
        self.assertNotContains(res, ">Tasks</a>")

    # ---------- admin status changes on the report edit page ----------

    def admin_set_report_status(self, status):
        admin = User.objects.create_user("admin", password="pass12345", is_staff=True)
        self.login(admin)
        return self.client.post(reverse("main:report_update", args=[self.report.pk]), {
            "title": self.report.title,
            "waste_type": self.report.waste_type,
            "severity": self.report.severity,
            "latitude": self.report.latitude,
            "longitude": self.report.longitude,
            "status": status,
        })

    def test_admin_reopening_report_puts_it_back_on_pending_list(self):
        CollectionTask.claim(self.report, self.official).close("Collected two bags.")
        self.admin_set_report_status("REPORTED")
        self.assertFalse(CollectionTask.objects.exists())

        self.login(self.other_official)
        self.assertContains(self.client.get(reverse("dispatch:pending_reports")), "Rice behind the canteen")
        self.assertIsNotNone(CollectionTask.claim(self.report, self.other_official))

    def test_admin_resolving_report_closes_open_task(self):
        task = CollectionTask.claim(self.report, self.official)
        self.admin_set_report_status("RESOLVED")
        task.refresh_from_db()
        self.assertEqual(task.status, CollectionTask.Status.CLOSED)
        self.assertEqual(task.closing_note, "Marked as resolved by an admin.")

    def test_reporter_editing_claimed_report_keeps_task(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.citizen)
        self.client.post(reverse("main:report_update", args=[self.report.pk]), {
            "title": "Rice and bread behind the canteen",
            "waste_type": "FOOD",
            "severity": "HIGH",
            "latitude": self.report.latitude,
            "longitude": self.report.longitude,
        })
        task.refresh_from_db()
        self.report.refresh_from_db()
        self.assertEqual(self.report.title, "Rice and bread behind the canteen")
        self.assertEqual(self.report.status, WasteReport.Status.IN_PROGRESS)
        self.assertTrue(task.is_open)

    
    # ---------- read-only task view for non-officials ----------

    def test_citizen_can_view_task_read_only(self):
        task = CollectionTask.claim(self.report, self.official)
        task.notes = "Internal: bring two bags"
        task.save()
        self.login(self.citizen)
        res = self.client.get(self.task_url("task_detail", task))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Rice behind the canteen")
        self.assertNotContains(res, "Internal: bring two bags")
        self.assertNotContains(res, self.task_url("task_close", task))
        self.assertNotContains(res, reverse("dispatch:my_tasks"))

    def test_report_page_links_citizens_to_progress(self):
        task = CollectionTask.claim(self.report, self.official)
        self.login(self.citizen)
        res = self.client.get(reverse("main:report_detail", args=[self.report.pk]))
        self.assertContains(res, self.task_url("task_detail", task))
        self.assertNotContains(res, "Claim for collection")

    def test_anonymous_task_detail_sent_to_login(self):
        task = CollectionTask.claim(self.report, self.official)
        res = self.client.get(self.task_url("task_detail", task))
        self.assertEqual(res.status_code, 302)