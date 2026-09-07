from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Household
from chores.forms import ChoreForm
from chores.models import Chore

User = get_user_model()


class ChoreTestCase(TestCase):
    """Two households, so every test can prove isolation between them."""

    def setUp(self):
        self.household = Household.objects.create(name="Casa")
        self.admin = User.objects.create_user("alice", password="pw", household=self.household, is_household_admin=True)
        self.roommate = User.objects.create_user("bob", password="pw", household=self.household)
        self.other_household = Household.objects.create(name="Other")
        self.other_admin = User.objects.create_user("zed", password="pw", household=self.other_household, is_household_admin=True)

        self.chore = Chore.objects.create(
            household=self.household, title="Dishes", points=5,
            recurrence=Chore.Recurrence.DAILY, rotation_start_member=self.admin, created_by=self.admin,
        )
        self.other_chore = Chore.objects.create(
            household=self.other_household, title="Lawn", points=10,
            recurrence=Chore.Recurrence.WEEKLY, rotation_start_member=self.other_admin, created_by=self.other_admin,
        )

    def payload(self, **overrides):
        return {"title": "Vacuum", "points": 3, "recurrence": "weekly", "rotation_start_member": self.roommate.pk, **overrides}


class ChoreModelTests(ChoreTestCase):
    def test_str_and_deadline_labels(self):
        self.assertEqual(str(self.chore), "Dishes")
        self.assertEqual(self.chore.deadline_label, "Every day by 23:59")
        self.assertEqual(self.other_chore.deadline_label, "Sunday by 23:59")

    def test_rotation_start_member_must_belong_to_household(self):
        self.chore.rotation_start_member = self.other_admin
        with self.assertRaises(ValidationError) as ctx:
            self.chore.full_clean()
        self.assertIn("rotation_start_member", ctx.exception.message_dict)

    def test_points_must_be_at_least_one(self):
        self.chore.points = 0
        with self.assertRaises(ValidationError) as ctx:
            self.chore.full_clean()
        self.assertIn("points", ctx.exception.message_dict)

    def test_paused_chores_sort_after_active_ones(self):
        Chore.objects.create(household=self.household, title="Aardvark care", points=1, recurrence="daily", is_paused=True)
        self.assertEqual([c.title for c in self.household.chores.all()], ["Dishes", "Aardvark care"])

    def test_rotation_order_is_join_order(self):
        early = User.objects.create_user("early", password="pw", household=self.household)
        early.date_joined = timezone.now() - timedelta(days=30)
        early.save()
        self.assertEqual(list(self.household.rotation_order()), [early, self.admin, self.roommate])

    def test_deleting_rotation_start_member_keeps_chore(self):
        self.chore.rotation_start_member = self.roommate
        self.chore.save()
        self.roommate.delete()
        self.chore.refresh_from_db()
        self.assertIsNone(self.chore.rotation_start_member)


class ChoreFormTests(ChoreTestCase):
    def test_rotation_choices_limited_to_own_household(self):
        form = ChoreForm(household=self.household)
        self.assertCountEqual(form.fields["rotation_start_member"].queryset, [self.admin, self.roommate])

    def test_member_of_other_household_rejected(self):
        form = ChoreForm(self.payload(rotation_start_member=self.other_admin.pk), household=self.household)
        self.assertFalse(form.is_valid())
        self.assertIn("rotation_start_member", form.errors)


class ChoreListViewTests(ChoreTestCase):
    url = reverse("chore_list")

    def test_requires_login(self):
        self.assertRedirects(self.client.get(self.url), f"{reverse('login')}?next={self.url}")

    def test_lists_only_own_household_chores(self):
        self.client.force_login(self.roommate)
        response = self.client.get(self.url)
        self.assertContains(response, "Dishes")
        self.assertContains(response, "Every day by 23:59")
        self.assertNotContains(response, "Lawn")

    def test_roommate_sees_no_admin_actions(self):
        self.client.force_login(self.roommate)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse("chore_create"))
        self.assertNotContains(response, reverse("chore_update", args=[self.chore.pk]))
        self.assertNotContains(response, "Pause")

    def test_admin_sees_actions(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, reverse("chore_create"))
        self.assertContains(response, reverse("chore_update", args=[self.chore.pk]))
        self.assertContains(response, reverse("chore_delete", args=[self.chore.pk]))
        self.assertContains(response, reverse("chore_toggle_pause", args=[self.chore.pk]))

    def test_paused_badge(self):
        self.chore.is_paused = True
        self.chore.save()
        self.client.force_login(self.roommate)
        response = self.client.get(self.url)
        self.assertContains(response, '<span class="badge">Paused</span>')
        self.assertNotContains(response, "Active</span>")

    def test_nav_marks_chores_as_current(self):
        self.client.force_login(self.roommate)
        self.assertContains(self.client.get(self.url), f'href="{self.url}" aria-current="page"')

    def test_user_without_household_sees_empty_state(self):
        self.client.force_login(User.objects.create_user("solo", password="pw"))
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No chores yet")


class ChoreAdminViewPermissionTests(ChoreTestCase):
    def protected_requests(self):
        pk = self.chore.pk
        return [
            ("get", reverse("chore_create")),
            ("get", reverse("chore_update", args=[pk])),
            ("get", reverse("chore_delete", args=[pk])),
            ("post", reverse("chore_create")),
            ("post", reverse("chore_update", args=[pk])),
            ("post", reverse("chore_delete", args=[pk])),
            ("post", reverse("chore_toggle_pause", args=[pk])),
        ]

    def test_anonymous_is_sent_to_login(self):
        for method, url in self.protected_requests():
            response = getattr(self.client, method)(url)
            self.assertRedirects(response, f"{reverse('login')}?next={url}", msg_prefix=f"{method} {url}")

    def test_roommate_is_forbidden_and_nothing_changes(self):
        self.client.force_login(self.roommate)
        for method, url in self.protected_requests():
            response = getattr(self.client, method)(url, self.payload())
            self.assertEqual(response.status_code, 403, f"{method} {url}")
        self.chore.refresh_from_db()
        self.assertEqual(Chore.objects.count(), 2)
        self.assertEqual(self.chore.title, "Dishes")
        self.assertFalse(self.chore.is_paused)

    def test_toggle_pause_rejects_get(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("chore_toggle_pause", args=[self.chore.pk])).status_code, 405)


class ChoreAdminViewTests(ChoreTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_create(self):
        response = self.client.post(reverse("chore_create"), self.payload(), follow=True)
        self.assertRedirects(response, reverse("chore_list"))
        chore = Chore.objects.get(title="Vacuum")
        self.assertEqual(chore.household, self.household)
        self.assertEqual(chore.created_by, self.admin)
        self.assertEqual(chore.rotation_start_member, self.roommate)
        self.assertEqual(chore.recurrence, Chore.Recurrence.WEEKLY)
        self.assertContains(response, "Added “Vacuum”.")

    def test_create_form_offers_only_household_members(self):
        response = self.client.get(reverse("chore_create"))
        self.assertContains(response, f'<option value="{self.roommate.pk}">bob</option>', html=True)
        self.assertNotContains(response, ">zed<")

    def test_create_rejects_zero_points(self):
        response = self.client.post(reverse("chore_create"), self.payload(points=0))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Chore.objects.filter(title="Vacuum").exists())
        self.assertIn("points", response.context["form"].errors)

    def test_update(self):
        url = reverse("chore_update", args=[self.chore.pk])
        self.assertContains(self.client.get(url), "Edit “Dishes”")
        response = self.client.post(url, self.payload(title="Dishes & pans", recurrence="daily"))
        self.assertRedirects(response, reverse("chore_list"))
        self.chore.refresh_from_db()
        self.assertEqual(self.chore.title, "Dishes & pans")
        self.assertEqual(self.chore.rotation_start_member, self.roommate)
        self.assertEqual(self.chore.created_by, self.admin)  # untouched by edit

    def test_delete(self):
        url = reverse("chore_delete", args=[self.chore.pk])
        self.assertContains(self.client.get(url), "Delete “Dishes”?")
        response = self.client.post(url)
        self.assertRedirects(response, reverse("chore_list"))
        self.assertFalse(Chore.objects.filter(pk=self.chore.pk).exists())
        self.assertTrue(Chore.objects.filter(pk=self.other_chore.pk).exists())

    def test_toggle_pause_round_trip(self):
        url = reverse("chore_toggle_pause", args=[self.chore.pk])
        self.client.post(url)
        self.assertTrue(Chore.objects.get(pk=self.chore.pk).is_paused)
        response = self.client.post(url, follow=True)
        self.assertFalse(Chore.objects.get(pk=self.chore.pk).is_paused)
        self.assertContains(response, "Resumed “Dishes”.")

    def test_other_households_chores_are_404_for_every_action(self):
        pk = self.other_chore.pk
        for method, name in (
            ("get", "chore_update"), ("post", "chore_update"),
            ("get", "chore_delete"), ("post", "chore_delete"),
            ("post", "chore_toggle_pause"),
        ):
            response = getattr(self.client, method)(reverse(name, args=[pk]), self.payload())
            self.assertEqual(response.status_code, 404, f"{method} {name}")
        self.other_chore.refresh_from_db()
        self.assertEqual(self.other_chore.title, "Lawn")
        self.assertFalse(self.other_chore.is_paused)
