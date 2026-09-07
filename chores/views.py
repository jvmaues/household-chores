from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import household_admin_required

from .forms import ChoreForm
from .models import Chore


@login_required
def dashboard(request):
    # Placeholder so login has somewhere to land; task #7 builds the real dashboard.
    return render(request, "chores/dashboard.html")


@login_required
def chore_list(request):
    household = request.user.household
    chores = (
        Chore.objects.filter(household=household).select_related("rotation_start_member")
        if household is not None
        else Chore.objects.none()
    )
    return render(request, "chores/chore_list.html", {"chores": chores})


def _own_chore_or_404(request, pk):
    # Every chore lookup is scoped to the caller's household; other households' ids 404.
    return get_object_or_404(Chore, pk=pk, household=request.user.household)


@household_admin_required
def chore_create(request):
    form = ChoreForm(request.POST or None, household=request.user.household)
    if request.method == "POST" and form.is_valid():
        chore = form.save(commit=False)
        chore.created_by = request.user
        chore.save()
        messages.success(request, f"Added “{chore.title}”.")
        return redirect("chore_list")
    return render(request, "chores/chore_form.html", {"form": form, "chore": None})


@household_admin_required
def chore_update(request, pk):
    chore = _own_chore_or_404(request, pk)
    form = ChoreForm(request.POST or None, instance=chore, household=request.user.household)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Saved “{chore.title}”.")
        return redirect("chore_list")
    return render(request, "chores/chore_form.html", {"form": form, "chore": chore})


@household_admin_required
def chore_delete(request, pk):
    chore = _own_chore_or_404(request, pk)
    if request.method == "POST":
        title = chore.title
        chore.delete()
        messages.success(request, f"Deleted “{title}”.")
        return redirect("chore_list")
    return render(request, "chores/chore_confirm_delete.html", {"chore": chore})


@household_admin_required
@require_POST
def chore_toggle_pause(request, pk):
    chore = _own_chore_or_404(request, pk)
    chore.is_paused = not chore.is_paused
    chore.save(update_fields=["is_paused"])
    verb = "Paused" if chore.is_paused else "Resumed"
    messages.success(request, f"{verb} “{chore.title}”.")
    return redirect("chore_list")
