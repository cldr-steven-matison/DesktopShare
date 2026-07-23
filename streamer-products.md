# Streamer Products — Market Research (Plan)

**Status (2026-07-23): research only, nothing built.** Written to catalog what streamers actually spend money on beyond hardware — plugins, overlays, bots, AI tools, platform features, SaaS subscriptions — so there's a real reference for where the market's money moves before deciding if any of it is worth building toward from the `cso-operator-app` streamers module ([`cso-operator-app-streamers.md`](cso-operator-app-streamers.md)) or the roster-cross-reference work in [`streamers-viral.md`](streamers-viral.md).

Scope is deliberately software/service spend, not hardware (capture cards, mics, cameras) — that's a different, much-covered market. Everything below is either a recurring SaaS subscription, a one-time plugin/asset purchase, a platform-native monetization feature, or a marketplace product.

---

## 1. All-in-one overlay/alert platforms

The center of gravity for most streamers' toolchain — free core tier, paid tier for premium assets/branding.

| Product | Model | What it does | Pricing |
|---|---|---|---|
| **StreamElements** | Cloud-first, browser-based | Overlays, alerts, chatbot, tipping page, loyalty points, merch store (via Fourthwall integration), multistreaming, activity feed | Free core; premium overlay packs and merch cuts on top |
| **Streamlabs** | Desktop app built on OBS | Bundles alerts, overlays, chat, merch, tipping, mobile streaming into one app | Free core; **Streamlabs Ultra** $189/yr unlocks premium overlay/theme library, advanced alert customization, mobile app, multistreaming |
| **Fourthwall** | Merch/membership-first, stream-integrated | Branded shop (print-on-demand + custom merch), memberships, tips, on-stream alert triggers for purchases | No monthly/annual fee — 3% on digital products, 5% on memberships, 0% on merch sales |

Split in philosophy: Streamlabs sells "one app for everything," StreamElements sells "cloud tools + huge free template library," Fourthwall has become the default answer specifically for merch/membership commerce and now competes directly with Streamlabs there.

---

## 2. Chatbots & moderation

| Product | Positioning | Notes |
|---|---|---|
| **Nightbot** | Beginner default | Cloud-hosted, spam/link filtering, easiest setup |
| **Moobot** | Long-standing (14+ yrs, pre-dates modern Twitch) | Cloud-based, heavily customizable auto-mod |
| **Fossabot** | Growing-channel tier | Handles very high message throughput, strong spam filtering, custom blocked-terms lists |
| **Streamer.bot** | Power-user tier | Local app, deep automation/integration (OBS scene control, TTS, points systems) — this is the one that starts overlapping with what a custom NiFi/backend pipeline could replace |
| **StreamElements bot / Streamlabs Cloudbot** | Bundled-in | Comes free with the all-in-one platforms above, decent for most channels that don't need Streamer.bot-level automation |

Common progression: Nightbot/Moobot to start → Fossabot once chat volume grows → Streamer.bot or the bundled StreamElements/Streamlabs bot once the streamer wants real automation, not just moderation.

---

## 3. OBS plugins & production software

Free, but worth tracking since they're the actual functional upgrades streamers install over stock OBS:

| Plugin | Category | What it adds |
|---|---|---|
| **Aitum Multistream** | Multistreaming | Push one OBS output to Twitch/YouTube/Kick/TikTok simultaneously — the fastest-growing reason streamers add a plugin at all in 2026 |
| **Advanced Scene Switcher** | Automation | Rule-based scene switching (hands-free) |
| **Move / Move Transition** | Visual | Animated source movement/transitions |
| **Source Record** | Production | Per-source recording independent of the main output |
| **Audio Monitor** | Audio | Per-source audio monitoring |
| **ReaPlugs VST FX** | Audio | Mic processing — EQ, compression, pitch |
| **obs-shaderfilter** | Visual FX | Custom shaders on any source — drop shadows, VHS look, pixelation, zoom blur, RGB split |
| **Aitum Vertical** | Content repurposing | 9:16 output for TikTok/Shorts/Reels alongside the main 16:9 stream |
| **LocalVocal** | Accessibility | Offline, multilingual live captions |

Notable: this is the layer where a streamer's *software* stack starts looking like a lightweight version of what our own pipeline already does server-side (Whisper transcription ≈ LocalVocal's captioning, clip/vertical repurposing ≈ our `ProcessClips`/caption flow).

---

## 4. AI clipping & highlight tools

This category is the closest direct analog to `cso-operator-app`'s streamers module — same problem (find the good moment, cut it, caption it, repost it), sold as a subscription instead of self-hosted.

| Product | Angle | Notes |
|---|---|---|
| **Opus Clip** | Long-form → vertical shorts | Best known for automatic "virality scoring" highlight detection; strong for podcasts/interviews as well as gameplay |
| **Eklipse** | Gaming-specific | Auto-detects kills/reactions/key moments directly from Twitch VODs, free tier, positions itself as "#1 AI highlight maker for streamers" |
| **StreamYard** | Default hub (per 2026 recommendation) | AI clipping bundled into a broader recording/streaming platform |
| **Streamlabs Highlighter** | Bundled-in | Included with the Streamlabs ecosystem rather than sold standalone |
| **Sizzle.gg, Mootion** | Alternative highlight tools | Smaller players in the same space |

Worth reading twice: this is literally the commercial version of `FetchClips → ProcessClips → PublishClip`. Our pipeline already does clip fetch, Whisper transcription, vLLM captioning, and X publish server-side and self-hosted — the market rate for the closest commercial equivalent (Opus Clip-tier) is a monthly SaaS fee per seat. Not proposing anything here, just flagging the overlap is real.

---

## 5. Hardware-companion software

Software tied to specific hardware purchases, but the thing being "bought" is really the software layer:

| Product | Ties to | What it does |
|---|---|---|
| **Elgato Stream Deck Marketplace** | Stream Deck hardware | Hundreds of plugins — scene transitions, overlay toggles, chat tools, soundboards |
| **Elgato Wave Link (+ Stream Deck plugin)** | Wave mics | Software mixer; the Stream Deck plugin turns physical keys/dials into a live mixing surface (per-channel mute/volume/effects) |
| **NVIDIA Broadcast** | RTX GPU | AI noise removal/suppression, virtual background, integrates directly into Wave Link's audio chain |
| **XSplit VCam** | Any webcam | Software-only green-screen removal, no physical green screen needed |

---

## 6. Stream-safe music licensing

Twitch/YouTube VOD copyright claims are a real, recurring cost driver — this whole category exists because of DMCA risk:

| Service | Model | Pricing |
|---|---|---|
| **Epidemic Sound** | Full commercial license library, Twitch-specific license covers live + VOD | $10.99/mo (creator tier) |
| **Soundstripe** | 10,000+ tracks + ~100k SFX | $9.99/mo (Personal), $19.99/mo (Pro, adds stems + commercial licensing) |
| **Pretzel Rocks** | Purpose-built streaming music player with Twitch chat integration | $4.99/mo for full library |
| **StreamBeats, Monstercat** | Free/curated stream-safe alternatives | Free or bundled |

---

## 7. VTuber-specific tools

A whole parallel product category once a streamer goes avatar-based instead of camera-based:

| Product | Format | Role |
|---|---|---|
| **VTube Studio** | Live2D (2D) | The standard face-tracking app — webcam → facial expression/head/body tracking onto a 2D rig |
| **Warudo** | VRM (3D) | 3D avatar animation, more advanced tracking/scene integration than VSeeFace |
| **VSeeFace** | VRM (3D) | Lighter-weight 3D tracking alternative |
| **VRoid Studio** | VRM (3D), free | Build a complete 3D anime-style avatar from scratch in a few hours, exports VRM 1.0 |
| **Model marketplaces (Etsy, Stream Skins, etc.)** | Both | Pre-rigged Live2D/VRM models for sale, ranging free → $10,000+ for a full custom commission |

---

## 8. Analytics & stats tools

| Product | Focus |
|---|---|
| **SullyGnome** | Deep historical Twitch channel/game stats, data back to 2015 |
| **StreamElements built-in analytics** | Widget/overlay-level tracking tied to their own alert system |
| **Streams Charts** | Cross-platform benchmarking (Twitch/YouTube/Kick) |
| **TwitchMetrics / TwitchTracker** | Similar niche to SullyGnome — channel and game-level breakdowns |

---

## 9. Discord community tooling

Almost every serious streamer's Discord runs at least one of these, since the community server is where the parasocial relationship (and the Patreon/membership upsell) actually lives:

| Bot | Role | Pricing |
|---|---|---|
| **MEE6** | Moderation + leveling/XP + reaction roles, most widely used | Free core; $11.95/mo premium (AI features, unlimited custom commands) |
| **Carl-bot** | Advanced auto-mod (anti-raid, logging, autoresponders), more generous free tier (250 reaction roles) | Free core; $7.99/mo premium |
| **Streamlabs (Discord bot)** | Stream-live notifications into Discord | Bundled with Streamlabs |
| **Nightbot** | Same bot bridged into Discord as Twitch chat, for cross-posting commands | Free |

---

## 10. Platform-native monetization (not third-party, but still "products" streamers opt into)

### Twitch
- **Bits**: as of May 2026, available to *all* eligible streamers globally — no Affiliate/Partner requirement to enable cheering. Purchasable/cheerable directly from the Twitch mobile app.
- **Subscriptions**: predictable recurring revenue, offset by monthly churn — most new streamers get sub/Bits access from day one now.
- **Extensions with Bits monetization**: viewers spend Bits inside a broadcaster-enabled Extension for a specific action/product.
- **New for 2026**: Creator Badge Drops, **Custom Power-Ups** (viewers spend Bits to trigger creator-defined on-stream effects, creator sets the Bits cost), and expanded **Hype Train** formats — differentiated Hype Train types reportedly generate up to 2x the revenue of a standard one. Shared Chat streams can now run a Hype Train jointly across channels.

### Kick
- **95/5 subscription split** — the headline differentiator vs. Twitch, unchanged and still the core pitch as of 2026.
- **100% ad revenue** kept by the streamer.
- **Kick Creator Incentive Program (KCIP)**: evolved into Kick's primary retention tool in 2026, paying creators roughly $16–$32/hour under program terms.
- **Tips via tokens** (Kick's own virtual currency) as the direct real-time support mechanism.
- Slots/Casino category was cut from Partner Program payouts in March 2025 — still allowed as content, just not monetized through the partner program.

---

## 11. Multistreaming & distribution

- **Aitum Multistream** (OBS plugin, see §3) — push a single OBS output to Twitch + YouTube + Kick + TikTok at once. Free, fastest-growing plugin category for exactly this reason.
- **Restream** — SaaS multistreaming/analytics platform, same job as Aitum but hosted rather than a local plugin, plus its own highlight/clipping features.

---

## Where this overlaps with our own stack

Two categories above (§4 AI clipping/highlights, §3 captioning) are things `cso-operator-app`'s streamers module already does server-side and self-hosted, for a roster of tracked Twitch/Kick streamers, rather than as a per-streamer subscription tool. Not proposing a pivot — just noting that if there's ever a reason to package any part of the existing pipeline (Whisper transcription, vLLM captioning, clip fetch/post) as a standalone product, Opus Clip/Eklipse pricing is the market comparable to benchmark against, and Streamer.bot is the closest analog on the automation side rather than the clipping side.

## Next steps

Nothing actionable yet — this is the reference doc. If a specific angle (e.g., "is there a wedge in the AI-clipping space," or "what would it take to add a Fourthwall-style merch tie-in to the streamers module") turns into real work, that becomes its own plan doc, and this one gets linked from it rather than expanded in place.

---

## Sources

- [Best StreamElements Alternatives in 2026](https://meldstudio.co/blog/best-streamelements-alternatives-in-2026/)
- [Streamlabs vs StreamElements 2026](https://earnifyhub.com/blog/streamlabs-vs-streamelements)
- [7 Best OBS Plugins for Streaming in 2026 - Gumlet](https://www.gumlet.com/learn/best-obs-plugins/)
- [Best OBS Plugins Every Streamer Should Be Using in 2026](https://onestream.live/blog/best-obs-plugins-every-streamer-should-use/)
- [Best OBS Plugins for Streamers in 2026 (Ranked by Impact) | VPE](https://getvpe.com/resources/blog/best-obs-plugins)
- [Monetization for All — Twitch Blog](https://blog.twitch.tv/en/2026/05/13/monetization-for-all/)
- [Twitch Bits guide 2026 | Gyre](https://gyre.pro/blog/twitch-bits-guide-what-are-they-and-how-to-earn)
- [The Best Hype Train Settings for Small Streamers (Plus Blerp)](https://blerp.com/blog/post/best-hype-train-settings-small-streamers)
- [Best AI Video Clipping Tools in 2026 | StreamYard](https://streamyard.com/blog/best-ai-video-clipping-tools-2026)
- [#1 AI Highlight Maker for Streamers — Eklipse](https://eklipse.gg/features/ai-highlights/)
- [Best AI Clipping Tools 2026 (Opus Clip, Eklipse & Free Options)](https://www.clipaffiliates.com/blog/best-ai-clipping-tools)
- [VTuber Model Pricing in 2026](https://news.viverse.com/post/vtuber-model-pricing-2026)
- [Best VTuber Software in 2026 | Kudos](https://kudos.tv/blogs/stream-blog/the-best-vtuber-software)
- [Introducing Fourthwall — StreamElements blog](https://blog.streamelements.com/introducing-fourthwall-a-better-solution-for-merch-1ea3a3a65d7d)
- [Streamlabs Ultra vs Fourthwall](https://coloradoplays.com/streamlabs-ultra-vs-fourthwall-merch/)
- [Top Nightbot Alternatives in 2026 — Slashdot](https://slashdot.org/software/p/Nightbot/alternatives)
- [9 Best Twitch Bots Ranked! 2026 Guide — StreamScheme](https://www.streamscheme.com/best-twitch-bots/)
- [Wave Link Plugin for Stream Deck — Elgato](https://www.elgato.com/us/en/explorer/products/wave/wave-link-plugin-for-stream-deck/)
- [Elgato x NVIDIA](https://www.elgato.com/ww/en/s/nvidia)
- [Royalty Free Music For Streamers — Full Resource List 2026](https://www.streamscheme.com/royalty-free-music-twitch/)
- [Pretzel Rocks — for Pro streamers](https://www.pretzel.rocks/for/pro)
- [How to Grow and Make Money on Kick in 2026 | Streams Charts](https://streamscharts.com/news/how-grow-and-make-money-kick-2026)
- [Kick Monetization in 2026: Full Requirements & 95/5 Split](https://streamerperks.com/blog/kick-monetization-explained-2026)
- [Best Streaming Tools in 2026 — The Complete Stack | VPE](https://getvpe.com/resources/blog/best-streaming-tools-2026)
- [SullyGnome overview, pricing, and alternatives — ACT](https://allcreatortools.com/tools/sullygnome)
- [Best Discord Bots in 2026 — CommunityOne](https://blog.communityone.io/best-discord-bots/)
- [MEE6 vs Carl-bot 2026 — PeakBot](https://peakbot.pro/blog/mee6-vs-carl-bot-comparison-2026)
