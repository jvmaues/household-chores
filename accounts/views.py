from django.conf import settings
from django.contrib.auth import login
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render

from .forms import SignUpForm
from .models import Household


def signup(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    # Single household per deployment: the first registrant creates it.
    household = Household.objects.first()
    if household is not None and household.is_full:
        return render(request, "registration/household_full.html", {"household": household})

    form = SignUpForm(request.POST or None, household=household)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
        except ValidationError as exc:
            # Model-level capacity check tripped (e.g. a concurrent sign-up).
            form.add_error(None, exc)
        else:
            login(request, user)
            return redirect(settings.LOGIN_REDIRECT_URL)

    return render(
        request,
        "registration/signup.html",
        {"form": form, "household": household, "max_members": Household.MAX_MEMBERS},
    )
