from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def household_admin_required(view_func):
    """Allow only the household administrator; anonymous users go to login, roommates get 403."""

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_household_admin:
            raise PermissionDenied("Only the household administrator can do this.")
        return view_func(request, *args, **kwargs)

    return _wrapped
