Daily chores are due at **23:59**. I’ll make the remaining low-impact product choices.

**Homework scope: Shared Household Chores — MVP**

A responsive web app for one household of up to six people. The first registered user creates the household and becomes its sole administrator; each account belongs to only one household.

* Administrator creates, edits, deletes, pauses, and assigns chore rotations.
* All members, including the administrator, participate in the rotation.
* Chores have a title, fixed point value, recurrence (daily or weekly), and deadline.
* Weekly cycles begin Monday. Daily chores stay with the same assignee for that week; weekly chores rotate each Monday.
* Roommates view current-week assignments, mark their assigned chore complete, and wait for administrator approval.
* The administrator approves or rejects submissions; rejection returns the chore to the same roommate.
* Approved chores award fixed points. Rankings show current-week points and reset every Monday.
* Overdue chores automatically transfer to the next roommate without penalizing the original assignee.
* Dashboard emphasizes current chores and deadlines, with visible overdue items and pending approvals.
* Screens: Dashboard, Chores, Weekly Ranking, and Account/Household Management.
* Notifications are limited to in-app reminders and overdue indicators.

Assumptions: deadlines use the household’s local timezone; a weekly chore is due Sunday at 23:59; paused chores neither rotate nor earn points.

Out of scope: photo evidence, email/push notifications, custom recurrences, multiple administrators/households, detailed reports, comments, and point penalties.
