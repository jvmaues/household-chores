from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from accounts.models import Household


class Chore(models.Model):
    class Recurrence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    # Deadlines are fixed by the spec: daily chores at 23:59, weekly ones Sunday 23:59.
    DEADLINE_LABELS = {
        Recurrence.DAILY: "Every day by 23:59",
        Recurrence.WEEKLY: "Sunday by 23:59",
    }

    household = models.ForeignKey(Household, on_delete=models.CASCADE, related_name="chores")
    title = models.CharField(max_length=100)
    points = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Awarded when the administrator approves the chore.",
    )
    recurrence = models.CharField(max_length=10, choices=Recurrence.choices)
    is_paused = models.BooleanField(default=False)
    rotation_start_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="rotation starts with",
        help_text="Members then take turns in the order they joined the household.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        editable=False,
        on_delete=models.SET_NULL,
        related_name="chores_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["is_paused", "title"]

    def __str__(self):
        return self.title

    @property
    def deadline_label(self):
        return self.DEADLINE_LABELS[self.Recurrence(self.recurrence)]

    def clean(self):
        super().clean()
        if (
            self.rotation_start_member_id
            and self.household_id
            and self.rotation_start_member.household_id != self.household_id
        ):
            raise ValidationError(
                {"rotation_start_member": "Must be a member of this household."}
            )
