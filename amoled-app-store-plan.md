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

**Explicitly deferred, not blocking #224**: whether future app development stays in
`waveshare-devices/apps/` with a per-release export to the split repos, or moves to developing
directly in each split repo going forward. No sync pipeline exists yet and none is being built as
part of this pass — decide it when the first post-split app update actually happens.

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
