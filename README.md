<p align="center">
  <img src="static/img/logo.svg" width="72" alt="Household Chores logo">
</p>

# Household Chores

A small, responsive web app for one household (up to six people) to share chores.
The administrator sets up chores and rotations, roommates mark their chores done,
the administrator approves them, and points feed a weekly ranking that resets every Monday.

Built with **Django 6.1** on **Python 3.13**, server-rendered templates and plain CSS — no JavaScript build step.

## How it works

- The **first person to sign up creates the household** and becomes its only administrator; everyone after that joins as a roommate. Each account belongs to exactly one household.
- **Chores** have a title, a fixed point value and a recurrence: *daily* (due every day by 23:59) or *weekly* (due Sunday by 23:59), in the household's local timezone.
- Weeks start on Monday. Daily chores keep the same assignee all week; weekly chores rotate each Monday. Rotation order is the order members joined; the administrator picks who starts each chore.
- Roommates mark a chore complete and the administrator **approves** (points awarded) or **rejects** (back to the same roommate).
- **Overdue** chores move to the next roommate automatically, without penalising the original assignee.
- **Paused** chores neither rotate nor earn points.

The full scope and assumptions live in [`_docs/plan.md`](_docs/plan.md); the build order in [`_docs/backlog.md`](_docs/backlog.md).

## Status

| Area | State |
|---|---|
| Custom user model, `Household`, 6-member limit, one administrator | done |
| Sign-up / log in / log out, `household_admin_required` | done |
| Responsive layout, blue/gray theme, household-timezone middleware | done |
| Chores: create / edit / delete / pause, read-only list for roommates | done |
| Weekly assignments, rotation, overdue transfer (`chores_tick`) | next |
| Dashboard, complete → approve/reject, weekly ranking, household screen | planned |

## Getting started

Requires Python 3.13. Either a plain virtualenv:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

or, if you use [`uv`](https://docs.astral.sh/uv/), the same steps through it (it picks up `.venv/` automatically):

```bash
uv venv && uv pip install -r requirements.txt
uv run python manage.py migrate
uv run python manage.py runserver
```

Open <http://127.0.0.1:8000/>, sign up, and you're the administrator of a new household.
Share the URL with your roommates; they'll join it when they sign up.

`manage.py createsuperuser` gives you a login for Django's admin at `/admin/` (handy for inspecting data; it isn't part of the app's own flow).

## Running the tests

```bash
.venv/bin/python manage.py test          # or: uv run python manage.py test
```

Tests live in `accounts/tests.py` and `chores/tests/`. They cover the member limit and admin constraints, the sign-up/login flow, the timezone middleware, the base layout, and chore permissions across two households.

## Project layout

```
household_chores/   settings, root URLs, WSGI/ASGI
accounts/           User (custom), Household, sign-up/login, timezone middleware, admin decorator
chores/             Chore model, Chores screen, dashboard placeholder (assignments, ranking to come)
templates/          base.html and the auth pages
static/             app.css (theme) and img/logo.svg
_docs/              plan.md (scope) and backlog.md (tasks)
```

## Things worth knowing

- **`AUTH_USER_MODEL = "accounts.User"`** — set before the first migration. `User.household` is a nullable FK and `User.is_household_admin` is enforced unique per household at the database level.
- **One household per deployment.** Sign-up creates the household only if none exists yet; later registrants join it, and the seventh is turned away.
- **Times are always local to the household.** `accounts.middleware.HouseholdTimezoneMiddleware` activates the household's IANA timezone on every request, so templates render local times without any per-view work. The footer shows which timezone is active.
- **Admin-only views** use `@household_admin_required` (`accounts/decorators.py`): anonymous → login, roommate → 403. Every chore lookup is also scoped to the caller's household, so other households' ids simply 404.
- **Development settings only.** `DEBUG` is on and the secret key is the generated one; hardening is a backlog item.
