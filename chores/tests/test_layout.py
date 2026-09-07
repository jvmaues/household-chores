from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse

from accounts.models import Household

User = get_user_model()


class BaseLayoutTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Casa", timezone="Europe/Lisbon")
        self.admin = User.objects.create_user("alice", password="pw", household=self.household, is_household_admin=True)
        self.roommate = User.objects.create_user("bob", password="pw", household=self.household)

    def test_authenticated_nav_has_all_four_screens(self):
        self.client.force_login(self.roommate)
        response = self.client.get(reverse("dashboard"))
        for label, href in (("Dashboard", reverse("dashboard")), ("Chores", "/chores/"), ("Ranking", "/ranking/"), ("Household", "/household/")):
            self.assertContains(response, f'href="{href}"', msg_prefix=label)
            self.assertContains(response, f">{label}</a>")
        self.assertContains(response, "Log out")
        self.assertNotContains(response, "Sign up")

    def test_current_page_is_marked(self):
        self.client.force_login(self.roommate)
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, f'href="{reverse("dashboard")}" aria-current="page"')

    def test_anonymous_nav_offers_login_and_signup(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, f'href="{reverse("login")}"')
        self.assertContains(response, f'href="{reverse("signup")}"')
        self.assertNotContains(response, "Ranking")

    def test_admin_badge_only_for_administrator(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("dashboard")), '<span class="badge">admin</span>')
        self.client.force_login(self.roommate)
        self.assertNotContains(self.client.get(reverse("dashboard")), '<span class="badge">admin</span>')

    def test_footer_shows_household_timezone(self):
        self.client.force_login(self.roommate)
        self.assertContains(self.client.get(reverse("dashboard")), "Times shown in Europe/Lisbon")

    def test_footer_shows_default_timezone_for_anonymous(self):
        self.assertContains(self.client.get(reverse("login")), "Times shown in UTC")

    def test_stylesheet_is_linked_and_exists(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'href="/static/css/app.css"')
        self.assertIsNotNone(finders.find("css/app.css"))

    def test_messages_are_rendered_with_level_class(self):
        html = render_to_string(
            "base.html",
            {"messages": [Message(constants.SUCCESS, "Chore saved.")], "user": AnonymousUser()},
        )
        self.assertIn('class="message message--success"', html)
        self.assertIn("Chore saved.", html)

    def test_viewport_meta_for_mobile(self):
        self.assertContains(self.client.get(reverse("login")), 'name="viewport"')


class BrandingTests(TestCase):
    def test_logo_asset_exists(self):
        self.assertIsNotNone(finders.find("img/logo.svg"))

    def test_header_shows_logo_mark_and_favicon(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'class="brand__mark" src="/static/img/logo.svg"')
        self.assertContains(response, 'rel="icon" type="image/svg+xml" href="/static/img/logo.svg"')

    def test_auth_pages_show_logo(self):
        for name in ("login", "signup"):
            self.assertContains(self.client.get(reverse(name)), 'class="auth-card__logo"', msg_prefix=name)
