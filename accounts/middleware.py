from django.utils import timezone


class HouseholdTimezoneMiddleware:
    """
    Activate the household's timezone for the duration of each request so every
    rendered datetime is local to the household.

    Must sit after AuthenticationMiddleware. Anonymous users and users without a
    household fall back to settings.TIME_ZONE. The timezone is always reset
    afterwards so nothing leaks between requests on the same thread.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        household = getattr(request.user, "household", None)
        if household is not None:
            timezone.activate(household.tzinfo)
        else:
            timezone.deactivate()
        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()
