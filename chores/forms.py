from django import forms

from .models import Chore


class ChoreForm(forms.ModelForm):
    class Meta:
        model = Chore
        fields = ("title", "points", "recurrence", "rotation_start_member")

    def __init__(self, *args, household, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rotation_start_member"].queryset = household.rotation_order()
        self.fields["rotation_start_member"].empty_label = None
        if self.instance.pk is None:
            # Lets Chore.clean() validate membership before the view saves.
            self.instance.household = household
