# streamer-kb seed — clip metadata off the `/clips` PVC (#278)

One-time, read-only pull from the live `cso-operator-app` pod on `cso-prod-1`, 2026-08-30, for the
per-streamer retrieval index on the DGX Spark (#271, K2). No MP4s, no queue files — `.pending_publish.json`
was deliberately not read. Nothing here is a credential: clip ids, titles, logins, X handles, tweet ids,
in-pod paths, transcripts and captions.

| File | Source | Entries | Per-entry keys |
|---|---|---|---|
| `gif_index.json` | `/clips/.gif_index.json` (dict keyed by `clip_id`) | 150 | `clip_id, streamer, source, title, url, thumbnail_url, view_count, created_at, x_handle, gif_path, gif_bytes, crop_why, cut_start, cut_dur, gif_error, indexed_at` (+ `tweet_url, tweet_id, posted_at` once posted) |
| `published_history.json` | `/clips/.published_history.json` (list, last 500) | 500 | `clip_id, title, source, streamer, url, thumbnail_url, x_handle, tweet_id, tweet_url, published_at` |
| `processed_clips.jsonl` | Kafka topic `processed_clips` (3 partitions, full scan, no consumer group) | 144 | `clip_id, streamer, source, title, transcript, caption, caption_mode, quote_reason, created_at, url, duration, view_count, _ts` — the richest seed: transcript + caption per clip |

`streamer` is the bare login; `source` is `twitch` / `kick` — together they are the `login` / `kick:login`
streamer key (`_parse_watch_entry`). Pull commands: `kubectl exec deploy/cso-operator-app -- cat /clips/<file>`
piped through `python3 -m json.tool`; the topic dump was a one-off `AIOKafkaConsumer` full scan run inside the
pod (the `backfill_metadata` / `clip_queue` pattern in `backend/services/streamers.py`), messages without a
transcript dropped.
