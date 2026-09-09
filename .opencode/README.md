# opencode integration for DesktopShare

This directory contains the opencode-specific integration for the DesktopShare repo on NvidiaSpark-1 (DGX Spark).

## Files

- `opencode.json` — opencode configuration with GitHub integration
- `startup.sh` — session startup script (git pull + inbox + repo context)
- `spark-session.sh` — wrapper to start opencode with GitHub integration

## Usage

```bash
# Start opencode with inbox and GitHub integration
bash .opencode/spark-session.sh [message]

# Or manually
bash .opencode/startup.sh && opencode --dir /home/tunas/BrainShare
```

## GitHub Integration

The integration uses the GitHub API via `gh` CLI (already authenticated on this box). Every session:
1. Runs `git pull --ff-only`
2. Lists inbox issues (`device:NvidiaSpark-1`)
3. Shows repo snapshot (branch, head, open issues count)
4. Checks EFM flow status
5. Checks MiNiFi agent status
