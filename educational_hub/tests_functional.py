"""Browser tests for the Educational Hub (headless Chrome via Selenium).

Skipped when Selenium or Chrome is unavailable, e.g. in CI.
Run only these with: python manage.py test educational_hub.tests_functional
"""
from unittest import SkipTest, mock, skipUnless

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import tag
from django.urls import reverse

from .models import Article
from .tests import LONG_TEXT, SAMPLE_CSV, FakeResponse

try:
    from selenium import webdriver
    from selenium.common.exceptions import WebDriverException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError:
    webdriver = None


@tag("functional")
@skipUnless(webdriver, "selenium is not installed")
class HubBrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = webdriver.ChromeOptions()
        for argument in ("--headless=new", "--window-size=1280,900", "--disable-gpu"):
            options.add_argument(argument)
        try:
            cls.browser = webdriver.Chrome(options=options)
        except WebDriverException as error:
            super().tearDownClass()
            raise SkipTest(f"Chrome is not available: {error.msg}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    def setUp(self):
        cache.clear()
        self.alice = User.objects.create_user("alice", password="pass12345")
        self.article = Article.objects.create(
            author=self.alice, title="Composting at home", category="COMPOSTING", content=LONG_TEXT
        )
        Article.objects.create(author=self.alice, title="Sorting packaging", category="SORTING", content=LONG_TEXT)

    def open(self, url_name, *args):
        self.browser.get(self.live_server_url + reverse(url_name, args=args))

    def find(self, selector):
        return self.browser.find_element(By.CSS_SELECTOR, selector)

    def wait_for(self, condition, timeout=8):
        return WebDriverWait(self.browser, timeout).until(lambda _driver: condition())

    def log_in(self):
        self.client.force_login(self.alice)
        self.open("main:landing")
        self.browser.add_cookie({"name": "sessionid", "value": self.client.cookies["sessionid"].value})

    def mark_page(self):
        self.browser.execute_script("window.__samePage = true")

    def is_same_page(self):
        return self.browser.execute_script("return window.__samePage === true")

    def card_titles(self):
        return [el.text for el in self.browser.find_elements(By.CSS_SELECTOR, ".educational-hub__card-title")]

    def test_search_filters_articles_without_reloading(self):
        self.open("education:article_list")
        self.wait_for(lambda: len(self.card_titles()) == 2)
        self.mark_page()
        self.find("input[name=q]").send_keys("packaging")
        self.wait_for(lambda: self.card_titles() == ["Sorting packaging"])
        self.assertTrue(self.is_same_page())
        self.assertIn("q=packaging", self.browser.current_url)

    def test_login_required_redirect_then_publish(self):
        self.open("education:article_create")
        self.wait_for(lambda: "/login/" in self.browser.current_url)
        self.wait_for(lambda: "Please log in first" in self.find("[data-toast]").text)

        self.find("input[name=username]").send_keys("alice")
        self.find("input[name=password]").send_keys("pass12345")
        self.browser.execute_script("document.querySelector('.login-section form').requestSubmit()")
        self.wait_for(lambda: self.browser.current_url == self.live_server_url + reverse("education:article_create"))
        self.wait_for(lambda: self.browser.find_elements(By.CSS_SELECTOR, "input[name=title]"))

        self.find("input[name=title]").send_keys("Freezing leftovers safely")
        self.find("textarea[name=content]").send_keys(LONG_TEXT)
        self.browser.execute_script("document.querySelector('form.educational-hub__form').requestSubmit()")
        self.wait_for(lambda: self.browser.execute_script(
            "var h = document.querySelector('h1'); return h && h.textContent.trim()"
        ) == "Freezing leftovers safely")
        self.assertTrue(Article.objects.filter(title="Freezing leftovers safely", author=self.alice).exists())

    def like_button(self):
        return self.find(f"#educational-hub-reactions-{self.article.pk} .educational-hub__reaction")

    def like_pressed(self):
        return self.browser.execute_script(
            "return document.querySelector('.educational-hub__reaction').getAttribute('aria-pressed')"
        )

    def test_like_flips_before_the_server_answers(self):
        self.log_in()
        self.open("education:article_detail", self.article.pk)
        self.wait_for(lambda: self.like_pressed() == "false")
        # htmx:beforeSend fires after the optimistic update but before the request leaves the browser.
        self.browser.execute_script(
            "document.body.addEventListener('htmx:beforeSend', function () {"
            "  window.__pressedBeforeSend = document.querySelector('.educational-hub__reaction').getAttribute('aria-pressed');"
            "}, { once: true });"
        )
        self.like_button().click()
        self.wait_for(lambda: self.browser.execute_script("return window.__pressedBeforeSend") == "true")
        self.wait_for(lambda: self.browser.execute_script(
            "return document.querySelector('.educational-hub__reaction-count').textContent.trim()"
        ) == "1")
        self.assertEqual(self.article.likes.count(), 1)

    def test_failed_like_is_rolled_back(self):
        self.log_in()
        self.open("education:article_detail", self.article.pk)
        self.wait_for(lambda: self.like_pressed() == "false")
        Article.objects.filter(pk=self.article.pk).delete()  # the next request now gets a 404
        self.like_button().click()
        self.wait_for(lambda: not self.find("#educational-hub-error").get_attribute("hidden"))
        self.assertEqual(self.like_pressed(), "false")
        self.assertIn("no longer exists", self.find("#educational-hub-error").text)

    def test_data_page_filters_without_reloading(self):
        with mock.patch("educational_hub.food_waste_data.urlopen", return_value=FakeResponse(SAMPLE_CSV)):
            self.open("education:food_waste_data")
            self.wait_for(lambda: "2 results for 2022" in self.find(".educational-hub__count").text)
            self.mark_page()
            self.find("input[name=q]").send_keys("bra")
            self.wait_for(lambda: [el.text for el in self.browser.find_elements(By.CSS_SELECTOR, "tbody th")] == ["Brazil"])
        self.assertTrue(self.is_same_page())
