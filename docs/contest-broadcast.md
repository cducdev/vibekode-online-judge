# Contest Broadcast Data

VKOJ provides a small broadcast-facing surface for recent submissions and
VNOI Resolver exports. Screen and webcam capture are separate media services;
these endpoints do not capture contestant devices.

## Live submissions

For a contest with key `<contest>`:

- `/contest/<contest>/submissions/live` is the normal live-submissions page.
- `/contest/<contest>/submissions/feed` is its JSON data source.
- `/contest/<contest>/submissions/live?embed=1&theme=dark` is the clean OBS
  browser-source view. Use `theme=light` for the light theme.

The feed returns at most five official, non-virtual submissions from the last
three minutes. It excludes submissions after the contest freeze time. Pending
submissions trigger a 1.5-second refresh interval; otherwise the client polls
every five seconds. When the event daemon is available, contest events trigger
an immediate refresh as well. The newest row animates once on initial load;
later refreshes animate only submission IDs that were not previously present.
New rows expand vertically while entering, so existing rows move down smoothly
instead of jumping before the fade animation starts.

Each row shows the contestant's full name when available, falling back to the
profile display name or username, plus the first listed organization, problem,
verdict with points, and submission time.

While a contest with configured hidden subtasks is running, public and
ranking-code viewers receive a masked verdict. The displayed score includes
only points earned on visible subtasks, weighted against the full problem
score, so it cannot reveal hidden-subtask results. Contest editors can see the
full verdict and score. The mask is removed for everyone after the contest
ends.

Access follows `Contest.can_see_full_scoreboard()`. A valid contest ranking
access code can also be supplied as `?code=<ranking_access_code>`. Append it to
the embed URL with `&code=...` when the broadcaster cannot use an authenticated
session. The code does not bypass private-contest access checks.

Treat the ranking access code as a credential. It can appear in OBS profiles,
logs, and screenshots, and it grants access to the contest's public ranking
view as well as this feed. Use an event-specific value, do not commit it, and
rotate or clear it after the broadcast.

Suggested OBS browser-source settings:

- URL: `https://<host>/contest/<contest>/submissions/live?embed=1&theme=dark`
- Width: `480`
- Height: `1440`
- Custom CSS: none

The embed always uses large broadcast typography and a two-row submission
layout. It hides the relative-time column so names and results remain readable
without depending on viewport-specific breakpoints.

Keep the regular contest ranking page as the scoreboard browser source and add
the recent-submissions embed as a separate browser source in the same OBS
scene. The ranking page intentionally does not embed the recent-submissions
panel.

## VNOI Resolver export

Export the final contest dataset with:

```sh
python manage.py export_vnoi_resolver_data <contest> /path/to/data.json
```

The command exports live participants, contest problems, and graded
submissions, excluding compile errors, internal errors, and virtual
participations. The resulting JSON can be loaded into
`VNOI-Admin/vnoi-resolver` for a frozen-scoreboard reveal ceremony.

This is a point-based VNOI Resolver export. The existing
`export_event_feed` management command remains available for tools consuming
the legacy CLICS XML event-feed format.

## Deployment

This feature has no database migration. Rebuild styles, compile translations,
collect static files, and restart the Django site after deployment. The event
daemon is recommended but optional because polling remains active as a
fallback.
