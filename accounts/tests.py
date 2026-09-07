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
