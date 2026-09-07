from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValidationError(f"'{value}' is not a valid IANA timezone.")


class Household(models.Model):
    MAX_MEMBERS = 6

    name = models.CharField(max_length=100)
    timezone = models.CharField(
        max_length=64,
        default="UTC",
        validators=[validate_timezone],
        help_text="IANA timezone name, e.g. Europe/Lisbon.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def tzinfo(self):
        return ZoneInfo(self.timezone)

    @property
    def member_count(self):
        return self.members.count()

    @property
    def is_full(self):
        return self.member_count >= self.MAX_MEMBERS

    def rotation_order(self):
        """Members in the order chores rotate through them: by join date."""
        return self.members.order_by("date_joined", "pk")


class User(AbstractUser):
    household = models.ForeignKey(
        Household,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )
    is_household_admin = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # The spec gives each household exactly one administrator.
            models.UniqueConstraint(
                fields=["household"],
                condition=Q(is_household_admin=True),
                name="one_admin_per_household",
            ),
            # An administrator must belong to a household.
            models.CheckConstraint(
                condition=Q(is_household_admin=False) | Q(household__isnull=False),
                name="admin_requires_household",
            ),
        ]

    def clean(self):
        super().clean()
        self._validate_household_capacity()

    def save(self, *args, **kwargs):
        # Enforce the limit even for saves that bypass forms/full_clean().
        self._validate_household_capacity()
        super().save(*args, **kwargs)

    def _validate_household_capacity(self):
        if self.household_id is None:
            return
        others = User.objects.filter(household_id=self.household_id)
        if self.pk is not None:
            others = others.exclude(pk=self.pk)
        if others.count() >= Household.MAX_MEMBERS:
            raise ValidationError(
                {"household": f"This household already has {Household.MAX_MEMBERS} members."}
            )
