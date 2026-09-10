**Cold start run 2026-09-10 — installed, proven, one thing left for root.**

`install.sh --cold-start` ran (after the fix in [f3df32a](https://github.com/cldr-steven-matison/DesktopShare/commit/f3df32a): the `/etc/init.d` stub had to leave, not just lose its rc links, or `systemctl enable` syncs SysV state through `update-rc.d` and aborts). Result on the box:

- `minifi-java.service` **enabled / active** on the native unit; the stub is in `/var/backups/`; `:8190` doors 200, `:9936` 200.
- `nvidia-serve-boot.service` and `nvidia-post-boot-verify.service` **enabled**; `dgx-spark-prometheus.service` **enabled / active** on `:9835` (#239).
- **The first cold start failed on vLLM, and that was the driver's fault, caught by its own health gate.** `vllm-serve.sh` pulled `vllm/vllm-openai:latest`, which had moved to **0.29.0** (`c2914767…`); it crash-looped 38 times on this config while the validated **0.28.0** (`61fc8a89…`) was on disk. The other five came up. qdrant floated to 1.19.1 the same way, harmlessly (both collections intact).
- Fix, commit [c246798](https://github.com/cldr-steven-matison/DesktopShare/commit/c246798): [`serve-boot.sh`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-322/serve-boot.sh) now pins `VLLM_IMAGE` (0.28.0), `TEI_IMAGE` and `QDRANT_IMAGE` (1.19.1, pinned forward) by digest. A boot never floats on `:latest` again; bump a pin on purpose after a validated run.
- **Proof, pinned driver from nothing:** all six containers destroyed and recreated, **all healthy in 5 m 41 s** (qdrant 2 s, tei-kb 15 s, tei-embed 15 s, tei-rerank 16 s, whisper 6 s, vLLM 5 m 35 s in the background). Verifier ([`post-boot-verify.sh --no-post`](https://github.com/cldr-steven-matison/DesktopShare/blob/main/files/issue-322/post-boot-verify.sh)): **20 passed, 1 failed** — every container, every port incl. qdrant `:6334`, 18/18 k3s pods, `:8190/embed` 200, the caption door alive (GET 405). The one FAIL is `unit nvidia-serve-boot: failed` — the unit's recorded state from the floating run; the script itself passed on the re-run.

**One root command clears that state** (or `restart` instead of `reset-failed` to re-prove through systemd, ~6 min of tier downtime):
```
sudo systemctl reset-failed nvidia-serve-boot
```

Acceptance: the mechanism is installed and proven from nothing on the pinned images. The real cold-boot criterion lands on the next reboot, which posts its own report here. Docs: [runbook §8](https://github.com/cldr-steven-matison/DesktopShare/blob/main/nvidia-dgx-spark-runbook.md), [CLAUDE-CHECKIN.md](https://github.com/cldr-steven-matison/DesktopShare/blob/main/CLAUDE-CHECKIN.md) §NvidiaSpark-1.
