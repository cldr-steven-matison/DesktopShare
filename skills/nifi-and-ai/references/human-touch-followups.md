# Things a Claude-built flow still needs a human pass on

Building a flow via the REST API gets the logic right, but it doesn't automatically get everything else right. This file is a running list of the specific things Steven has had to clean up by hand after a programmatic build — read it before claiming a build is "done," and add to it the next time something new turns up.

## Canvas layout / spacing

A programmatically-built flow is functionally correct but visually rough — processors land wherever the API call's `position` said, connections cross awkwardly, and it reads nothing like a hand-laid-out flow. **This is true even when x-coordinates are matched to a role/column and y is spaced consistently** — that discipline helps, but it does not eliminate the need for a manual align/tidy pass in the Designer or NiFi UI afterward. Don't claim a build is visually finished; say what it functionally does, and expect (or explicitly ask about) a follow-up cleanup pass.

Concrete practice, worth doing even though it doesn't fully replace the human pass:
- Match new processors' x-coordinates to the existing column for that processor role; read existing `position.x` values per role and reuse them.
- Vary only `y` per new step in a chain — one row per stage, consistent row height (150–200 units worked fine in practice).
- Branches (e.g. a live/not-live split) get their own x-offset columns, symmetric around the branch point, not arbitrary numbers.

Real example, 2026-07-23/24: the `WatchlistChatJoiner` PG was built with role-matched columns and consistent row spacing, and Steven still did a "processor sliding and human cleanup" pass afterward — worth noting explicitly rather than assuming good coordinates alone are enough.

## (add the next one here)
