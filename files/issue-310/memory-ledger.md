# Memory ledger — WindowsDesktop, 2026-09-08 (#310 / #247)

Every memory file in the three silos on this device, read in full and classified per
`agent/local-repo-unification.md`. **Class:** `dup` = already held by the repo (owner named) →
deleted; `promote` = held only here → written into the owner named, then deleted; `repo-wrong` =
the memory recorded a correction the repo never got → repo fixed, then deleted; `keep` → rewritten
terse as one of the four survivors. Backup of the pre-sweep state:
`~/.claude/backups/memory-optimize-2026-09-08-100020.tgz` (not committed).

Counts: DesktopShare silo 85 → 4 · cso-operator-app silo 9 → 0 · home-dir silo 6 → 0.

## Silo `-home-tunas-DesktopShare` (85)

### `feedback_*` — none survive; a lesson is never a memory (#310)

| memory | class | owner / promoted to |
|---|---|---|
| amoled_app_change_is_not_a_platform_rebuild | promote | `incident-rules.md` §Fixes (check in + cost); guard 15; known-patterns `amoled-rebuild` |
| amoled_flash_no_ask | keep (residue) + dup | flash paths/partitions → `amoled-this-device`; the no-ask rule is in `efm-waveshare-amoled.md` |
| automation_must_meet_curated_bar | promote | `streamers/streamers.md` GIF path facts (quality bar) |
| bias_to_empirical_test_over_research | promote | `incident-rules.md` §Fixes (cheap live test over research agents) |
| check_in_after_diagnosis | promote | `incident-rules.md` §Fixes |
| cso_prod_1_sizing_and_no_scope_notes | dup + promote | known-patterns `wsl-sizing`/`minikube-profile`; no-scope-notes → `writing-style.md` |
| diagnose_pattern_before_iterating_fixes | promote | `incident-rules.md` §Fixes |
| dont_gotcha_frame_scope_clarifications | promote | `writing-style.md` §Reporting work |
| dont_repeat_the_harm_while_verifying_fix | promote | `incident-rules.md` §Fixes |
| dont_replace_device_os | promote + dup | docs-are-facts/done/next → `writing-style.md`; the Brookesia-guest deliverable is `efm-waveshare-amoled.md` |
| files_dir_not_root | promote | `incident-rules.md` §Issue hygiene (`files/issue-<n>/`), guard 16 |
| generalize_incident_rules | dup | `skills/README.md` policy-vs-technique split; `writing-style.md` provenance strip |
| keep_work_streams_split | promote | `incident-rules.md` §Fixes (sibling issues before architecture) |
| kubectl_env_creds | promote | `incident-rules.md` §Credentials (value-vs-valueFrom mechanism) |
| look_at_the_artifact_before_guessing | promote | `incident-rules.md` §Fixes |
| match_existing_x_post_precedent | promote | `incident-rules.md` §Fixes (closest analog; build where Steven said) |
| nifi_live_state_authoritative | promote | `workflow.md` §Live infra vs. docs (Steven's PGs vs Claude-built PGs) |
| no_ai_credits_user_facing | promote | `writing-style.md` |
| no_askuserquestion_spam_troubleshooting | promote | `writing-style.md` (plain text during live debugging) |
| no_endpoints_for_oneoff_fixes | dup | `incident-rules.md` §Commits and workflow |
| no_manual_data_into_live_triggers | promote | `live-queues.md` (inert-probe rule) |
| no_module_flag_defaults | promote | `incident-rules.md` §Fixes (per-run flag principle) |
| no_real_phone_asks_in_tests | promote | `device-comms.md` §Session comms |
| parallel_board_builds | keep (residue) + dup | work-tree recipe → `amoled-this-device`; rule in known-patterns `amoled-rebuild` |
| port_change_fanout | dup | `streamers/cso-operator-app-streamers.md` (setup-streamers-flows.py fan-out) |
| prod_no_manual_patches | promote | `incident-rules.md` §Live service restarts (human-in-the-loop carve-out) |
| reply_brevity | promote | `writing-style.md` §Reporting work |
| research_before_web | promote | `workflow.md` §Finding the pattern (ladder before WebSearch) |
| review_must_apply_not_just_report | promote | `incident-rules.md` §Fixes |
| session16_trust_breakdown | dup | `incident-rules.md` §Fixes (do exactly what's asked; don't over-claim); `CLAUDE.md` universal rules |
| simulator_before_device_flash | dup | known-patterns `amoled` row; `tools/simulator/README.md` in waveshare-devices |
| streamers_doc_placement | promote | `streamers/README.md` (doc map: research vs implementation) |
| task_status_session_level | dup | `device-comms.md` §Working an issue (claim on pickup) |
| telegram_completion_notify | dup + promote | `device-comms.md` §Session comms; sendPhoto line added |
| use_context | dup | `CLAUDE.md` "Who's asking" + the lookup ladder |
| use_wall_script_not_adhoc_chromium | keep (residue) | `wall.sh` → `amoled-this-device` |
| verify_subagent_output_before_reporting | promote | `workflow.md` §Model, effort & context hygiene (4-step check) |
| wipe_speculative_cross_device_specs | promote | `incident-rules.md` §Fixes |
| writing_style | promote | `writing-style.md` (one Session entry per calendar day) |
| wslconfig_is_config_not_a_cap | dup | known-patterns `wsl-sizing` |

### `project_*`

| memory | class | owner / promoted to |
|---|---|---|
| amoled_devices_inbound | dup (stale) | per-board `hasBattery` is a profile field (`platform/profiles/README.md`) |
| amoled_panel_font_and_shell_facts | dup | `uikit/tokens.json` + lint rules R8–R10; `efm-waveshare-amoled.md` |
| amoled_platform | keep (residue) | `amoled-this-device`; docs `efm-waveshare-amoled.md`, `efm-amoled-capabilities.md` |
| beelink_mpv_stream_loader | dup | `completed/claude-screen.md`, `streamers/streamers-twitch-bot-mpv-plan.md` |
| cso_operator_modules_flag | promote | `cso-operator-app/CLAUDE.md` §Deploy (the exec check itself) |
| dgx_spark_226 | dup | `nvidia-dgx-spark-plan.md` and the #226 children |
| efm_agent_registry_fix_2026-07-18 | dup | `efm-operations-manual.md` (EFM Postgres read path) |
| efm_guide_sensorclass_device | dup (speculative) | guide tracker Ch20/21 |
| efm_kubernetespod_two_instances | promote | `CLAUDE-CHECKIN.md` WindowsDesktop local facts |
| efm_lastseen_not_live | dup | `efm-metrics.md`, `efm-observability.md` (heartbeat counter) |
| flink_agents_231 | dup | `files/cso-prod-1/VALIDATION.md` §#231, `flink-agents-cso-plan.md` |
| geticeberg_154_state | keep (residue) | `iceberg-on-this-box`; `CLAUDE-CHECKIN.md` |
| guard_hook_v3_192 | dup + promote | guard.sh header; the heredoc-loss gotcha → `device-comms.md` §Finishing |
| guide_humanization_295 | dup | `efm-guide-humanization-plan.md` + the guide tracker |
| microfi_devices_next | dup | `efm-xiao-microfi-1-2-3.md` |
| oauth_refresh_stops_getkickchannelid | dup | `streamers/cso-operator-app-streamers.md` |
| prod_cutover_253 | keep (residue) + dup | `~/cutover-stage-253` → `local-paths-and-quirks`/`CLAUDE-CHECKIN.md`; rest in `cso-prod-1-cutover-plan.md` §9 |
| queryiceberg_156_state | keep (residue) | `iceberg-on-this-box`; `queryiceberg-processor-plan.md` |
| sceneserver | dup | `CONTEXT.md`, `CLAUDE-CHECKIN.md` droplet block |
| streamers_brain_276_279 | dup | `streamers/streamers-new-brain-plan.md`, streamers doc Session 25–27 |
| streamers_gif_library_195 | promote | `streamers/streamers.md` GIF path facts |
| streamers_gif_path | promote | `streamers/streamers.md` GIF path facts |
| telegram_reply_bridge_192 | dup | `agent-to-agent.md`, `CLAUDE-CHECKIN.md` Telegram section |
| tuna_testing_vllm_crash_2026-07-13 | promote | `CLAUDE-CHECKIN.md` local facts (`VLLM_WSL2_ENABLE_PIN_MEMORY`) |
| twitch_chat_bot_stream_loader | dup + promote | `streamers/streamers-twitch-bot.md`; the classifier note → `CLAUDE-CHECKIN.md` |
| x_live_rtmp_pipeline | keep | `x-live-pipeline`; `CLAUDE-CHECKIN.md` |
| zellij_tunnel_sudo_blocks_efm | promote | `incident-rules.md` §Port-forwards; `CLAUDE-CHECKIN.md` |

### `reference_*` and `user_*`

| memory | class | owner / promoted to |
|---|---|---|
| app_url | promote | `CLAUDE-CHECKIN.md` (tunnel vs port-forward on :8090) |
| efm_flow_designer_api | dup | skill `references/minifi-efm.md` §7 |
| efm_kafka_external_access | dup | `incident-rules.md` §Port-forwards; `CLAUDE-CHECKIN.md` |
| giphy_channel | promote | `streamers/streamers.md` GIF path facts |
| headless_p_no_notification_hook | dup | `agent-to-agent.md`, `CLAUDE-CHECKIN.md` |
| headless_ui_screenshots | repo-wrong + promote | said `~/Downloads`; replaced by `files/headless-shot.mjs` + known-patterns `screenshot` |
| kafka_ops | promote | `cso-operator-app/CLAUDE.md` §Kafka topics |
| nifi_api_access | promote | skill `references/flow-api.md` (capability probe) |
| nifi_custom_processor_toolchain | promote | skill `references/custom-processors.md` (CS auto-stop, provenance DELETE) |
| nifi_flowjson_vs_param_refs | dup | skill rule 1 carve-out, `flow-api.md` §5, canon |
| nifi_processor_local_copy_stale | repo-wrong + promote | sources moved to `streamers/nifi-processors/` (`CLAUDE.md` table fixed); rebase-on-deployed → skill |
| nifi_python_processor_version_switch | promote | skill `references/custom-processors.md` step 4 |
| repositories | dup | `CLAUDE-CHECKIN.md` path map, `CLAUDE.md` repo table |
| twitch_refresh_token_behavior | dup | `streamers/streamers-twitch-bot.md` §14 |
| waveshare_devices_repo | dup | `efm-waveshare-amoled.md`, `amoled-app-store-plan.md` |
| windows_minifi_python_binaries | promote | `CLAUDE-CHECKIN.md` local facts |
| user_steven_matison | dup | `CLAUDE.md` "Who's asking", `CONTEXT.md` |

## Silo `-home-tunas-cso-operator-app` (9) → 0

| memory | class | owner / promoted to |
|---|---|---|
| feedback_gif_and_clip_quality_bar | promote | `streamers/streamers.md` GIF path facts |
| feedback_modules_deploy_value | dup | `cso-operator-app/CLAUDE.md` §Deploy |
| feedback_nifi_trickle_over_batch | promote | `cso-operator-app/CLAUDE.md` §Kafka topics (trickle line) |
| project_fetchclips_rotation_fix | dup | `streamers/cso-operator-app-streamers.md` Session 22; app `CLAUDE.md` |
| project_gif_identity_refs_weak | promote | `streamers/streamers.md` GIF path facts |
| project_prod_vllm_3b_not_7b_awq | repo-wrong | `CLAUDE-CHECKIN.md`, `files/cso-prod-1/VALIDATION.md`, `files/cso-prod-1/vllm.yaml` corrected; app `CLAUDE.md` `VLLM_MODEL` line |
| reference_issues_live_in_desktopshare | promote | `cso-operator-app/CLAUDE.md` (last paragraph) |
| reference_nifi_python_extensions_deploy | dup | skill `references/custom-processors.md` |
| reference_openclaw_bash_echoes_stdout | dup | `files/agent-lib.sh` header, `streamers/README.md` "Operating it" |

## Silo `-home-tunas` (6) → 0

| memory | class | owner / promoted to |
|---|---|---|
| feedback_credits | dup | `writing-style.md` (no AI credits) |
| feedback_shutdown_complete | keep (merged) | `x-live-pipeline`; `CLAUDE-CHECKIN.md` |
| project_livestream_x | keep (merged) | `x-live-pipeline`; `CLAUDE-CHECKIN.md` |
| project_megamini_oled_rgb | dup | `completed/hacking-the-geekom-g1.md` |
| project_sceneserver | dup | `CONTEXT.md`, `CLAUDE-CHECKIN.md` |
| user_profile | dup | `CLAUDE.md`, `CONTEXT.md` |

## Survivors (DesktopShare silo)

`amoled-this-device` · `x-live-pipeline` · `iceberg-on-this-box` · `local-paths-and-quirks` — each
`type: reference`, ≤ 15 body lines, `approved: 2026-09-08 https://github.com/cldr-steven-matison/DesktopShare/issues/310`
(this sweep was Steven's explicit ask on #310; new memories after it go through
`files/memory-propose.sh`).
