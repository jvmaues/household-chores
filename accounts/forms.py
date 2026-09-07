from zoneinfo import available_timezones

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import Household, User

TIMEZONE_CHOICES = [(tz, tz) for tz in sorted(available_timezones())]


class SignUpForm(UserCreationForm):
    """
    Registration form for the single-household deployment.

    Pass ``household=None`` when no household exists yet: the registrant
    names it, picks its timezone, and becomes the administrator. Pass the
    existing household otherwise: the registrant joins it as a roommate and
    the household fields are removed from the form.
    """

    household_name = forms.CharField(max_length=100, label="Household name")
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES, initial="UTC")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, household=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.household = household
        if household is not None:
            del self.fields["household_name"]
            del self.fields["timezone"]

    def clean(self):
        cleaned = super().clean()
        if self.household is not None and self.household.is_full:
            raise ValidationError(
                f"{self.household.name} already has {Household.MAX_MEMBERS} members."
            )
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.household is None:
            user.household = Household.objects.create(
                name=self.cleaned_data["household_name"],
                timezone=self.cleaned_data["timezone"],
            )
            user.is_household_admin = True
        else:
            user.household = self.household
        if commit:
            user.save()
        return user
