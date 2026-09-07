from zoneinfo import ZoneInfo

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from .models import Household

User = get_user_model()


def make_user(username, household=None, **extra):
    return User.objects.create_user(username=username, password="pw", household=household, **extra)


class HouseholdTests(TestCase):
    def test_tzinfo_returns_zoneinfo(self):
        household = Household.objects.create(name="Home", timezone="Europe/Lisbon")
        self.assertEqual(household.tzinfo, ZoneInfo("Europe/Lisbon"))

    def test_invalid_timezone_fails_validation(self):
        household = Household(name="Home", timezone="Mars/Olympus_Mons")
        with self.assertRaises(ValidationError) as ctx:
            household.full_clean()
        self.assertIn("timezone", ctx.exception.message_dict)

    def test_member_count_and_is_full(self):
        household = Household.objects.create(name="Home")
        self.assertEqual(household.member_count, 0)
        self.assertFalse(household.is_full)
        for i in range(Household.MAX_MEMBERS):
            make_user(f"u{i}", household)
        self.assertEqual(household.member_count, Household.MAX_MEMBERS)
        self.assertTrue(household.is_full)


class UserModelTests(TestCase):
    def test_custom_user_model_is_active(self):
        self.assertEqual(User._meta.label, "accounts.User")

    def test_user_without_household_is_allowed(self):
        user = make_user("solo")
        user.full_clean()
        self.assertIsNone(user.household)
        self.assertFalse(user.is_household_admin)

    def test_deleting_household_detaches_members(self):
        household = Household.objects.create(name="Home")
        user = make_user("alice", household)
        household.delete()
        user.refresh_from_db()
        self.assertIsNone(user.household)


class MemberLimitTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Home")
        for i in range(Household.MAX_MEMBERS):
            make_user(f"u{i}", self.household)

    def test_seventh_member_rejected_on_save(self):
        with self.assertRaises(ValidationError):
            make_user("u7", self.household)
        self.assertEqual(self.household.member_count, Household.MAX_MEMBERS)

    def test_seventh_member_rejected_on_full_clean(self):
        user = User(username="u7", household=self.household)
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn("household", ctx.exception.message_dict)

    def test_existing_member_can_still_be_saved(self):
        member = self.household.members.first()
        member.first_name = "Renamed"
        member.full_clean()
        member.save()  # must not count itself toward the limit
        member.refresh_from_db()
        self.assertEqual(member.first_name, "Renamed")

    def test_moving_member_to_full_household_rejected(self):
        other = Household.objects.create(name="Other")
        newcomer = make_user("newcomer", other)
        newcomer.household = self.household
        with self.assertRaises(ValidationError):
            newcomer.save()


class AdminConstraintTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Home")

    def test_only_one_admin_per_household(self):
        make_user("alice", self.household, is_household_admin=True)
        with self.assertRaises(IntegrityError):
            make_user("bob", self.household, is_household_admin=True)

    def test_second_household_can_have_its_own_admin(self):
        make_user("alice", self.household, is_household_admin=True)
        other = Household.objects.create(name="Other")
        make_user("bob", other, is_household_admin=True)  # must not raise

    def test_admin_requires_household(self):
        with self.assertRaises(IntegrityError):
            make_user("nobody", None, is_household_admin=True)


class AdminRegistrationTests(TestCase):
    def test_models_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(User))
        self.assertTrue(admin.site.is_registered(Household))

    def test_admin_changelists_render(self):
        superuser = User.objects.create_superuser("root", "root@example.com", "pw")
        self.client.force_login(superuser)
        for url in ("/admin/accounts/user/", "/admin/accounts/household/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)


# --- Task 2: registration, login, logout, admin decorator -------------------

from django.contrib.auth.models import AnonymousUser  # noqa: E402
from django.core.exceptions import PermissionDenied  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from django.urls import reverse  # noqa: E402

from .decorators import household_admin_required  # noqa: E402
from .forms import SignUpForm  # noqa: E402

STRONG_PW = "correct-horse-battery-staple"


def signup_payload(username, **extra):
    return {"username": username, "password1": STRONG_PW, "password2": STRONG_PW, **extra}


class SignUpFlowTests(TestCase):
    def test_first_registrant_creates_household_and_becomes_admin(self):
        response = self.client.post(
            reverse("signup"),
            signup_payload("alice", household_name="Casa", timezone="Europe/Lisbon"),
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="alice")
        self.assertTrue(user.is_household_admin)
        self.assertEqual(user.household.name, "Casa")
        self.assertEqual(user.household.timezone, "Europe/Lisbon")
        self.assertEqual(Household.objects.count(), 1)
        # Logged in automatically.
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_first_registrant_must_name_the_household(self):
        response = self.client.post(reverse("signup"), signup_payload("alice"))
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "household_name", "This field is required.")
        self.assertFalse(User.objects.exists())
        self.assertFalse(Household.objects.exists())

    def test_second_registrant_joins_as_roommate(self):
        household = Household.objects.create(name="Casa")
        make_user("alice", household, is_household_admin=True)

        response = self.client.post(reverse("signup"), signup_payload("bob"))
        self.assertRedirects(response, reverse("dashboard"))
        bob = User.objects.get(username="bob")
        self.assertFalse(bob.is_household_admin)
        self.assertEqual(bob.household, household)
        self.assertEqual(Household.objects.count(), 1)

    def test_signup_form_hides_household_fields_when_joining(self):
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Create your household")
        self.assertIn("household_name", response.context["form"].fields)

        household = Household.objects.create(name="Casa")
        make_user("alice", household, is_household_admin=True)
        response = self.client.get(reverse("signup"))
        self.assertContains(response, "Join Casa")
        self.assertNotIn("household_name", response.context["form"].fields)
        self.assertNotIn("timezone", response.context["form"].fields)

    def test_seventh_registrant_is_blocked(self):
        household = Household.objects.create(name="Casa")
        for i in range(Household.MAX_MEMBERS):
            make_user(f"u{i}", household, is_household_admin=(i == 0))

        get = self.client.get(reverse("signup"))
        self.assertTemplateUsed(get, "registration/household_full.html")
        self.assertContains(get, "Casa is full")

        post = self.client.post(reverse("signup"), signup_payload("u7"))
        self.assertTemplateUsed(post, "registration/household_full.html")
        self.assertFalse(User.objects.filter(username="u7").exists())
        self.assertEqual(household.member_count, Household.MAX_MEMBERS)

    def test_password_mismatch_rejected(self):
        response = self.client.post(
            reverse("signup"),
            {"username": "alice", "password1": STRONG_PW, "password2": "different",
             "household_name": "Casa", "timezone": "UTC"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_authenticated_user_is_redirected_away_from_signup(self):
        household = Household.objects.create(name="Casa")
        self.client.force_login(make_user("alice", household))
        self.assertRedirects(self.client.get(reverse("signup")), reverse("dashboard"))


class SignUpFormTests(TestCase):
    def test_form_rejects_full_household_even_if_view_is_bypassed(self):
        household = Household.objects.create(name="Casa")
        for i in range(Household.MAX_MEMBERS):
            make_user(f"u{i}", household)
        form = SignUpForm(signup_payload("u7"), household=household)
        self.assertFalse(form.is_valid())
        self.assertIn("already has 6 members", str(form.non_field_errors()))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.household = Household.objects.create(name="Casa")
        self.user = make_user("alice", self.household)
        self.user.set_password(STRONG_PW)
        self.user.save()

    def test_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": STRONG_PW}
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_login_honours_next(self):
        response = self.client.post(
            reverse("login"), {"username": "alice", "password": STRONG_PW, "next": "/admin/"}
        )
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_bad_credentials_stay_on_login(self):
        response = self.client.post(reverse("login"), {"username": "alice", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logged_in_user_skips_login_page(self):
        self.client.force_login(self.user)
        self.assertRedirects(self.client.get(reverse("login")), reverse("dashboard"))

    def test_logout_requires_post_and_returns_to_login(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class LoginRequiredTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_dashboard_renders_role(self):
        household = Household.objects.create(name="Casa")
        self.client.force_login(make_user("alice", household, is_household_admin=True))
        response = self.client.get(reverse("dashboard"))
        self.assertContains(response, "the administrator")
        self.assertContains(response, "Casa")


class HouseholdAdminRequiredTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.household = Household.objects.create(name="Casa")
        self.admin = make_user("alice", self.household, is_household_admin=True)
        self.roommate = make_user("bob", self.household)
        self.view = household_admin_required(lambda request: HttpResponse("ok"))

    def _request(self, user):
        request = self.factory.get("/protected/")
        request.user = user
        return request

    def test_admin_allowed(self):
        self.assertEqual(self.view(self._request(self.admin)).content, b"ok")

    def test_roommate_forbidden(self):
        with self.assertRaises(PermissionDenied):
            self.view(self._request(self.roommate))

    def test_anonymous_redirected_to_login(self):
        response = self.view(self._request(AnonymousUser()))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))


# --- Task 3: household timezone middleware ---------------------------------

from datetime import datetime, timezone as dt_timezone  # noqa: E402

from django.conf import settings  # noqa: E402
from django.template import Context, Template  # noqa: E402
from django.utils import timezone as dj_timezone  # noqa: E402

from .middleware import HouseholdTimezoneMiddleware  # noqa: E402

NOON_UTC = datetime(2026, 1, 15, 12, 0, tzinfo=dt_timezone.utc)


class HouseholdTimezoneMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.household = Household.objects.create(name="Casa", timezone="America/Sao_Paulo")
        self.member = make_user("alice", self.household)

    def _run_request(self, user):
        """Run one request through the middleware; capture what a view would see."""
        seen = {}

        def get_response(request):
            seen["tz"] = dj_timezone.get_current_timezone_name()
            seen["rendered"] = Template("{{ dt|date:'Y-m-d H:i' }}").render(Context({"dt": NOON_UTC}))
            return HttpResponse()

        request = self.factory.get("/")
        request.user = user
        HouseholdTimezoneMiddleware(get_response)(request)
        return seen

    def test_member_sees_household_local_time(self):
        seen = self._run_request(self.member)
        self.assertEqual(seen["tz"], "America/Sao_Paulo")
        self.assertEqual(seen["rendered"], "2026-01-15 09:00")  # UTC-3

    def test_anonymous_falls_back_to_default_timezone(self):
        seen = self._run_request(AnonymousUser())
        self.assertEqual(seen["tz"], settings.TIME_ZONE)
        self.assertEqual(seen["rendered"], "2026-01-15 12:00")

    def test_user_without_household_falls_back_to_default_timezone(self):
        seen = self._run_request(make_user("solo"))
        self.assertEqual(seen["tz"], settings.TIME_ZONE)

    def test_timezone_is_reset_after_request(self):
        self._run_request(self.member)
        self.assertEqual(dj_timezone.get_current_timezone_name(), settings.TIME_ZONE)

    def test_middleware_is_installed_after_authentication(self):
        auth = settings.MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
        tz = settings.MIDDLEWARE.index("accounts.middleware.HouseholdTimezoneMiddleware")
        self.assertGreater(tz, auth)
