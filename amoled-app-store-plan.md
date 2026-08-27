# AMOLED App Store — framework + publishing apps individually

Execution plan for [issue #217](https://github.com/cldr-steven-matison/DesktopShare/issues/217).
Hand-off for the repo-creation half: [issue #224](https://github.com/cldr-steven-matison/DesktopShare/issues/224).
Platform golden source: [`efm-waveshare-amoled.md`](efm-waveshare-amoled.md). Board: the Waveshare
ESP32-S3-Touch-AMOLED-1.8 V2.

## Why this is one plan, not two

Right now every app iteration means patching `littlefs_data.bin` by hand, `write-flash 0xaa1000`,
hard reset — a flash cycle per change, the EFM agent drops every time, and anything not re-staged in
`examples/system/super/littlefs/` vanishes from the partition. #217 is about making the board's own
App Store client do this instead: drop a `.bpk`, install/update from the panel's Store tab, no
reflash. The board's five apps
(`tunastreet.agent`/`.racing`/`.tminus`/`.xviewer`/`.hello`) already live as subdirectories of one
repo, [`TunaStreetTest/waveshare-devices`](https://github.com/TunaStreetTest/waveshare-devices)
(`amoled-1.8-v2/apps/`), sharing one git history. "Publish and update them individually" is true in
two senses at once — the App Store's per-package versioned layout (`apps/<pkg>/versions/<ver>/`)
already updates one app without touching another's index entry, and on the publishing side each app
becoming its own repo with its own release history is the other half of "individually." #224 already
asked for that second half. This doc covers both; #224 gets a comment pointing back here for its
concrete task list.

**Execution**: WindowsDesktop. It's the only device with the board (COM8), the four app backends
(`192.168.1.121:8091`–`:8094`), and a `waveshare-devices` checkout at current HEAD — StarlinkAI's
local clone is 3 commits behind (missing `tunastreet.agent`/`.racing`/`.tminus`, the `uikit`, and the
`tools/simulator`), confirmed by reading the GitHub tree directly rather than trusting the stale
local copy. StarlinkAI does not have the board or the LAN backends to execute any of this itself.

## Part A — App Store framework (on-device mechanics)

From #217's own research: a `.bpk` is a ZIP with `manifest.json` at its root, named
`<package.id>.<debug|release>.<version>.bpk`. The store client reads `index.json` from a configured
root, then per-app `apps/<package_name>/versions/<version>/metadata.json`. Our four packages already
match this shape — publishing is zip + serve, not a rewrite.

Sequenced from #217's "Done when" checklist, spike first so the expensive step (the server) isn't
built before the packaging format is proven:

1. **Spike route B — USB sideload, no server at all.** `tools/brookesia_usb_cli install_bpk` over
   COM8 (`service/system/brookesia_service_usb`, `HostCommand::InstallBpk`, 8 MiB default max). One
   command, no partition write. This is also how the open signing question gets answered cheaply:
   `BROOKESIA_SYSTEM_CORE_ENABLE_PACKAGE_RELEASE_VERIFY` defaults to `y` and RSA-PSS-SHA256-verifies
   `.bpk`s at install — confirm here whether a debug-type package bypasses it, before route A depends
   on the answer.
2. **`make-bpk` tool**, next to `tools/stage_apps.py`: zips `apps/<id>/` into the correctly-named
   `.bpk`, version read out of that app's `manifest.json`.
3. **Self-hosted store server (route A)** — FastAPI on WindowsDesktop, same shape as the four app
   backends already on `:8091`–`:8094`. **Port `:8095`** — next free slot in that sequence (xviewer
   `:8091`, tminus `:8092` — reused from the retired `tunastreet.ember` backend, racing `:8093`, agent
   `:8094`). Note for later readers: this is WindowsDesktop's own port sequence; StarlinkAI separately
   uses `:8090`–`:8096` on a different host (`beelink-starlink-efm-ai.md`) for unrelated services — same
   numbers, different machines, not a conflict. New firewall rule `Allow AppStore Port 8095`, same
   trap as every other port here (mirrored networking exposes the bind, Windows Defender still blocks
   it without an explicit inbound rule).
4. Server serves `index.json` (`package_name`, `app_name`, `manifest_id`, `latest_version`,
   `description`, `categories`, `icon_url`, `bpk_url`, `size_download`, `updated_at` per app) plus
   `apps/<pkg>/versions/<ver>/metadata.json` and the `.bpk` files themselves.
5. Point `CONFIG_BROOKESIA_APP_STORE_INDEX_URL` at `http://192.168.1.121:8095/app_store/index.json`
   in `platform/sdkconfig.microfi`.
6. **Install, then update**, one app end-to-end from the panel's Store tab — verified on the glass,
   not just against the server.
7. Document the new path in `waveshare-devices/amoled-1.8-v2/tools/README.md`; demote the
   littlefs-patch recipe to "platform/shell changes only."

Espressif's public store (`brookesia-app-store.espressif.com`) stays out of scope — it's not ours to
publish to and there's no submission path in the source.

## Part B — Publish apps individually: split into public per-app repos

This is #224's scope, with the concrete list and rules below.

**Repos to create**, all under `TunaStreetTest` (where `waveshare-devices` already lives publicly —
not `steven-matison`, the personal account `amoled-x-ember` landed on by accident and stayed
private):

| New public repo | Source | Note |
|---|---|---|
| `amoled-agent` | `amoled-1.8-v2/apps/tunastreet.agent/` | agent status tile |
| `amoled-racing` | `amoled-1.8-v2/apps/tunastreet.racing/` | needs upstream-source credit, see below |
| `amoled-tminus` | `amoled-1.8-v2/apps/tunastreet.tminus/` | **fresh repo** — do not rename/transfer `steven-matison/amoled-x-ember` (Steven's call: retire that stray Ember-named repo, seed `amoled-tminus` clean) |
| `amoled-xviewer` | `amoled-1.8-v2/apps/tunastreet.xviewer/` | |
| `amoled-hello` | `amoled-1.8-v2/apps/tunastreet.hello/` | the runtime-package template — publish too (Steven's call): as far as we know the first Brookesia v0.8 runtime app outside Espressif, worth it as a minimal starter example even though it's not flashed to the device today |

**Mechanics**: `git subtree split --prefix=amoled-1.8-v2/apps/tunastreet.<name>` off
`waveshare-devices` `main`, push the split to the new repo — keeps each app's real commit history
instead of a flattened single initial commit.

**Every new repo gets:**
- The app's `manifest.json` / `app/` / `res/`.
- An `Apache-2.0` `LICENSE`, matching the `waveshare-devices` root license.
- A **rewritten public README** — the current in-tree READMEs were written for an internal audience
  and can't ship as-is:
  - Strip every `github.com/cldr-steven-matison/DesktopShare/issues/...` link. #224's rule ("No back
    reference to DesktopShare") is real, not incidental — `tunastreet.racing/README.md` currently
    links `#205`/`#201`/`#209`–`#213`, and `tunastreet.tminus`'s README (currently published, oddly,
    under `steven-matison/amoled-x-ember`) links `#184`. Both need those links removed for the public
    copy.
  - Add a link back to [`TunaStreetTest/waveshare-devices`](https://github.com/TunaStreetTest/waveshare-devices)
    as "runs on this platform" — the unified back-reference #224 asked for, pointed at the real
    platform repo.
  - **`amoled-racing` only** — credit
    [`cldr-jquiroscr/cloudera-racing-standalone`](https://github.com/cldr-jquiroscr/cloudera-racing-standalone)
    as the source of the game this panel app mirrors, and of its sprite art: `gen_racing_art.py`
    (`files/racing/` in DesktopShare) rasterises that repo's own inline SVGs rather than redrawing
    them. **Caveat worth flagging before this goes public**: that repo has no asserted license
    (`GET /repos/cldr-jquiroscr/cloudera-racing-standalone` returns `license.spdx_id: NOASSERTION`) —
    attribution alone doesn't establish redistribution rights for the vendored art. Word the credit as
    "inspired by / assets sourced from," and it's worth a quick check with the repo owner before
    `amoled-racing` ships publicly, rather than assuming the internal Cloudera-to-Cloudera courtesy
    extends to a public repo.

**`waveshare-devices` root `README.md`** gets a short "Apps" section added, linking out to all five
new repos — so the platform repo is the hub every app repo points back to, and vice versa.

## Part C — the per-app repo is the leader; the backend rides with it (resolved 2026-08-27)

The decision deferred at split time — "does future app development stay in
`waveshare-devices/apps/` with a per-release export, or move into each split repo" — got answered
the hard way. The first post-split updates (#236 xviewer, #222 tminus, and more) landed **only** in
standalone clones, never reached the leaders, and rode to `status:done`/closed anyway. Two commits
had to be recovered onto the leaders on 2026-08-27 after the fact.

**Resolved (Steven's call): the `TunaStreetTest/amoled-*` per-app repo is the leader for its app —
and it carries more than the device package.** Each leader now holds `apps/tunastreet.<n>/` **plus
`backend/`, `firmware/`, `simulator/`, `scripts/`** — none of which exist under
`waveshare-devices/amoled-1.8-v2/apps/`, which only ever held the on-device package half (`app/` +
`res/` + `manifest.json`). So:

- **The platform repo (`waveshare-devices`) does not track the backends at all.** A clean
  `waveshare-devices` tree is **not** proof the app shipped — the app + backend live in the leader
  repo, a *different* remote. Always check the leader.
- **An app and its backend are one unit.** Working the device app almost always means touching its
  backend (`:8091`–`:8094` on WindowsDesktop). Both are pushed to the **same** leader repo, together,
  before any status change.
- **`waveshare-devices` reduces to platform + hub, not an app-dev home.** It keeps only the true
  platform — board port (`platform/`), `uikit/`, `tools/`, boot screen — and the README "Apps"
  section linking out to the five leaders. App development moves **into the leader repo**; you edit
  `apps/tunastreet.<n>/` and `backend/` there, in one place, one push. The
  `amoled-1.8-v2/apps/tunastreet.<n>/` copies in `waveshare-devices` are the retired second home that
  caused this — they stop being a source of truth.

**Target state → what's left to collapse the competing homes** (the leaders already carry app +
backend, so no app work is at risk):

1. Retire the app source under `waveshare-devices/amoled-1.8-v2/apps/tunastreet.<n>/` — after
   confirming each leader's `apps/tunastreet.<n>/` is at or ahead of the `waveshare-devices` copy, so
   nothing is lost. `waveshare-devices` keeps `apps/tunastreet.hello/` only if it's still wanted as
   the in-repo template, or drops to a pointer to `amoled-hello`.
2. Re-clone the standalone dev clones (`~/amoled-agent`, `~/amoled-racing`, `~/amoled-x-viewer`,
   `~/amoled-tminus`) **from the leaders** so their local history matches — the paused cleanup pass.
3. The App-Store build (Part A) sources each `.bpk` from the leader's `apps/tunastreet.<n>/`, not
   from `waveshare-devices`.

**Close-ritual rule (mirrored into `agent/device-comms.md`):** before an AMOLED app/device issue
goes to `review` or `done`, confirm the **leader repo** (`TunaStreetTest/amoled-<app>`) has both the
app-package change **and** the backend change pushed to it — `git -C ~/amoled-<app> status` clean and
`git log --branches --not --remotes` empty is not enough when the local clone's history is unrelated
to the leader; verify against the leader's `main` directly.

## Done when

- [ ] USB sideload spike (route B) confirms our `.bpk` shape installs, and answers the signing
      question
- [ ] `make-bpk` tool exists next to `tools/stage_apps.py`
- [ ] Store server live on WindowsDesktop `:8095`, firewall rule in place, index lists all four
      shipped apps with icons
- [ ] `CONFIG_BROOKESIA_APP_STORE_INDEX_URL` set in `platform/sdkconfig.microfi`
- [ ] Install **and** update of one app verified end-to-end on the glass
- [ ] `waveshare-devices/amoled-1.8-v2/tools/README.md` documents the new path
- [x] Five repos created under `TunaStreetTest`, each public, `Apache-2.0`-licensed, with a rewritten
      README
- [ ] No `DesktopShare` issue links anywhere in the five new repos
- [ ] `amoled-racing`'s README credits `cldr-jquiroscr/cloudera-racing-standalone`, worded as
      "inspired by / sourced from," not as a license grant
- [x] `waveshare-devices` README links out to all five new repos
- [ ] `steven-matison/amoled-x-ember` left alone (private, retired) — not renamed, not transferred
