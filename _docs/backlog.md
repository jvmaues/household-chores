# Backlog — Shared Household Chores (Django MVP)

Derived from [plan.md](plan.md). Tasks are ordered so each builds on the previous one; each is meant to be a single, reviewable PR. Sizes: **S** ≈ half a day, **M** ≈ 1–2 days.

## Proposed app layout

| App | Owns |
|---|---|
| `accounts` | `User` (custom), `Household`, registration/login, Account & Household Management screen |
| `chores` | `Chore`, `Assignment`, rotation/overdue services, Dashboard, Chores, Weekly Ranking screens |

Django admin is used for back-office only; all roommate/administrator flows are built as regular views.

---

## Phase 0 — Foundation

### 1. Custom user model + Household — S
Must land before any other model is migrated (delete `db.sqlite3` and re-migrate from scratch).
- `accounts.User` extending `AbstractUser`, set as `AUTH_USER_MODEL`.
- `Household(name, timezone, created_at)` — one household per deployment.
- `User.household` (FK, nullable until they join) and `User.is_household_admin` (bool).
- Validation: at most 6 members per household.
- **Done when:** `migrate` from empty DB succeeds; both models visible in Django admin; tests cover the 6-member limit.

### 2. Registration, login, logout — S
- Sign-up form: if no household exists, the registrant names it, picks a timezone, and becomes the sole administrator; otherwise they join the existing household as a roommate (rejected when full).
- Login/logout via `django.contrib.auth` views; `LOGIN_URL`, `LOGIN_REDIRECT_URL` set.
- Reusable `household_admin_required` decorator for admin-only views.
- **Done when:** first user ends up admin, second ends up roommate, seventh is blocked; all app URLs require login.

### 3. Base layout + timezone middleware — S
- Responsive `base.html` with nav (Dashboard, Chores, Ranking, Household), messages framework output, minimal CSS (plain CSS or a classless stylesheet; no JS build step).
- `USE_TZ = True`; middleware that `timezone.activate()`s the household's timezone for each request so all displayed times are local.
- **Done when:** every subsequent screen extends `base.html` and renders local times.

---

## Phase 1 — Domain

### 4. Chore model + Chores screen — M
- `Chore(household, title, points, recurrence[DAILY|WEEKLY], is_paused, rotation_start_member, created_by, created_at)`.
- Rotation order = household members ordered by join date; admin picks the starting member per chore. (See decision #2.)
- Admin: create / edit / delete / pause / unpause. Roommates: read-only list.
- Chores screen shows title, recurrence, points, paused badge, and this week's assignee + status (status wired in task 5).
- **Done when:** admin can fully manage chores; roommates see but cannot mutate; permission tests pass.

### 5. Assignment model + weekly rollover service — M
- `Assignment(chore, assignee, week_start, due_at, status, points_awarded, submitted_at, reviewed_by, reviewed_at, rejection_count, transferred_from)`; statuses: `PENDING`, `SUBMITTED`, `APPROVED`, `TRANSFERRED`.
- `points_awarded` is snapshotted on approval so later chore edits don't rewrite history.
- Weekly chore → one Assignment per week, due Sunday 23:59 local. Daily chore → seven Assignments (Mon–Sun), same assignee, each due 23:59 local.
- `services.start_week(household, week_start)`: idempotent; skips paused chores; for each chore advances the rotation from the previous week's assignee (or uses `rotation_start_member` for the first week).
- **Done when:** unit tests cover rotation order, idempotency, paused chores skipped, and DST-safe 23:59 due times.

### 6. `chores_tick` command: rollover + overdue transfer — M
- Management command that (a) ensures the current week's assignments exist, then (b) for every `PENDING` assignment past `due_at`, marks it `TRANSFERRED` and creates a new `PENDING` assignment for the next roommate in rotation (no penalty to the original assignee). `SUBMITTED` items awaiting approval are *not* overdue.
- Transferred assignment is due 23:59 local the following day; the chain continues until submitted or the week ends. (See decision #1.)
- Run from cron/launchd every few minutes. Optional safety net: trigger a throttled tick on Dashboard load so a dev machine without cron still works.
- **Done when:** tests with frozen time prove transfer, non-penalty, and that submitted items are left alone.

---

## Phase 2 — Screens

### 7. Dashboard — M
- Roommate view: my assignments this week grouped as **Overdue / Due today / Later this week**, with deadline and a "Mark complete" action; items transferred away from me shown as informational.
- Administrator view adds a **Pending approvals** panel (count + link).
- In-app reminders: banner when something is due today; overdue and pending-approval badges reused across screens and in the nav.
- **Done when:** both roles see the right data; nothing from another household or a paused chore leaks in.

### 8. Mark complete + approve / reject — M
- Roommate: `POST /assignments/<id>/submit` — only own `PENDING` assignments → `SUBMITTED`.
- Admin approvals queue: approve → `APPROVED`, `points_awarded = chore.points`; reject → back to `PENDING` for the same roommate, `rejection_count += 1`, optional reason.
- All transitions in a single service module with explicit guards; views stay thin.
- **Done when:** state-machine tests cover every legal and illegal transition and cross-user access is denied.

### 9. Weekly Ranking — S
- Sum of `APPROVED` `points_awarded` per member for the current `week_start`, descending, ties by name; every member listed even at 0.
- Shows the week's date range and a "resets every Monday" note.
- **Done when:** view test confirms only the current week counts.

### 10. Account / Household Management — S
- Everyone: edit display name, change password.
- Admin: edit household name and timezone; member list with roles.
- Removing/transferring members is out of scope for MVP (would need rotation repair).
- **Done when:** roommates cannot reach the admin section.

---

## Phase 3 — Polish

### 11. Seed data + README — S
- `seed_demo` management command: one household, 4 users (1 admin), ~6 chores, current week's assignments, a couple of overdue/submitted items.
- README: setup, `runserver`, `chores_tick` cron line, demo credentials.
- **Done when:** a fresh clone reaches a populated Dashboard in under five commands.

### 12. Test sweep + hardening — S
- Fill gaps across rotation, overdue, approval, ranking, permissions; run `manage.py check --deploy` and fix what's reasonable (secret key from env, `ALLOWED_HOSTS`, `DEBUG` off in prod settings).
- **Done when:** the full suite passes and coverage of `services/` is near-complete.

---

## Decisions to confirm before Phase 1

1. **Due date of a transferred assignment.** Proposed: 23:59 local the next day, chain continues through Sunday. Alternative: keep the original deadline (already past, so it would immediately re-transfer — probably not wanted).
2. **Rotation order.** Proposed: members in join order, admin picks the starting member per chore. Alternative: admin drags members into an explicit per-chore order (more UI, better control).
3. **Daily chores as 7 rows/week.** Proposed because points, overdue, and approval are per-day events. Alternative: one row with per-day completion flags (fewer rows, more special-casing).
4. **Tick scheduling.** Proposed: management command on cron/launchd, with an optional throttled trigger on Dashboard load. Alternative: Celery beat (heavier than the MVP needs).
5. **Joining a household.** Proposed: single household per deployment, later registrants auto-join. Alternative: invite code, which becomes necessary the moment multiple households are ever wanted.
