**Setup Plan for Hermes Agent on Telegram (Parallel to OpenClaw)**

The goal is to run **Hermes Agent** in parallel with your existing OpenClaw setup on the same WSL2 Ubuntu environment. Everything uses the same local vLLM Qwen2.5-3B-Instruct (24k context) at `http://127.0.0.1:8000`. Telegram-first interface, coding tools enabled, elevated bash/exec access, and config tuned to match your OpenClaw workflow.

---

### Phase 1: Quick Hermes Install (WSL2)

```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
```

Reload shell:
```bash
source ~/.bashrc
```

Verify:
```bash
hermes --version
hermes doctor
```

---

### Phase 2: Telegram Bot Setup (New Bot for Parallel Use)

1. Open Telegram Desktop / phone → Message `@BotFather` → `/newbot`
2. Name it (e.g. `@hermes_tunastreet_bot`)
3. Copy the **bot token** (keep it secret).
4. (Optional but recommended) Use BotFather to set description, about text, commands, and avatar.
5. Disable privacy mode for group use (BotFather → /mybots → your bot → Bot Settings → Group Privacy → Turn off). Re-add bot to any groups after changing.

Find your numeric Telegram user ID:
- Message `@userinfobot` (it replies instantly with your ID).

---

### Phase 3: Hermes Gateway & Telegram Configuration

Run the interactive wizard (recommended):
```bash
hermes gateway setup
```

- Select **Telegram**
- Paste your new bot token
- Paste your numeric user ID (for `TELEGRAM_ALLOWED_USERS`)
- (Optional) Set home channel / group settings if using topics

**Manual .env alternative** (if wizard skipped):
```bash
cat > ~/.hermes/.env << EOF
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ALLOWED_USERS=your_numeric_user_id
TELEGRAM_REQUIRE_MENTION=true
EOF
```

Start the gateway (runs in background as systemd service):
```bash
hermes gateway install    # installs systemd service (first time only)
hermes gateway start
```

Check status:
```bash
hermes gateway status
```

---

### Phase 4: Onboarding & Model Configuration (Match OpenClaw)

Run full setup wizard:
```bash
hermes setup
```

Then configure the local Qwen model (OpenAI-compatible endpoint):
```bash
hermes model
```
- Choose **Custom / OpenAI-compatible**
- Base URL: `http://127.0.0.1:8000/v1`
- Model ID: `Qwen/Qwen2.5-3B-Instruct`
- API key: `none` (or leave blank)
- Context window: `32000`
- Max tokens: `8192`

Verify model:
```bash
hermes model list
curl http://localhost:8000/v1/models   # should show Qwen
```

---

### Phase 5: Tools & Security Configuration (Coding Profile)

Enable full coding tools and elevated execution:
```bash
hermes tools
```
- Select **coding** profile (or full)
- Explicitly enable: `exec`, `bash`, `read`, `write`, `edit`, `process`, `web_search`, etc.

Set elevated mode and security (mirrors your OpenClaw `yolo` preset):
```bash
hermes config set tools.exec.security full
hermes config set tools.exec.ask off
hermes approvals set --mode full --ask off
```

Unlock `/bash` and host command execution (similar to OpenClaw):
```bash
hermes config set commands.bash true
hermes config set tools.elevated.enabled true
hermes config set tools.elevated.allowFrom.telegram "your_numeric_user_id"
```

---

### Phase 6: Final Hermes Config & Restart

Check current config:
```bash
hermes config show
```

Apply any final tweaks via CLI or edit `~/.hermes/config.yaml` / `~/.hermes/.env` if needed.

Restart gateway to apply changes:
```bash
hermes gateway restart
```

---

### Phase 7: Test Hermes on Telegram

Open Telegram → message your new Hermes bot (or mention it in group with `requireMention: true`).

Test commands:
- `/status` — should show model, uptime, context
- `/bash kubectl config current-context`
- `/bash ls -la ~/DesktopShare`
- `/tools` — verify coding tools are active
- Send any normal message (agent should respond using local Qwen)

Both OpenClaw and Hermes will run in parallel on the same machine:
- OpenClaw on its Telegram bot (port 18789)
- Hermes on its own Telegram bot (gateway service)

---

### Quick Commands Reference (Hermes)

| Command                  | Purpose                              |
|--------------------------|--------------------------------------|
| `hermes gateway status`  | Check gateway                        |
| `hermes gateway restart` | Restart Telegram bot                 |
| `hermes model`           | Switch / configure local Qwen        |
| `hermes tools`           | Enable coding / exec tools           |
| `hermes claw migrate`    | (Optional) Import OpenClaw data     |
| `hermes doctor`          | Fix common issues                    |

**Done.** Your Hermes Agent is now live on Telegram, running in parallel with OpenClaw, using the exact same local vLLM Qwen stack. Test and iterate! 🚀