# Livestreamer — portable X live-stream pipeline (Windows + WSL2)

Self-contained bundle to bring the desktop-to-X live stream up on another Windows/WSL2 machine.
Everything the pipeline needs is in this one file: the runbook and the three scripts (extract with the
one-liner in step 4). Origin: `~/livestream.md` + `~/mediamtx/` on WindowsDesktop, snapshot 2026-09-08.

**Not in this file, on purpose:** the X stream key. This repo is public. Get the key from
X Media Studio -> Producer -> Sources (media.x.com) and put it in `X_KEY` in `stream-guard.sh` and on the
relay command line. The X public API has no live-broadcast endpoints, Media Studio is the only place.

## Pipeline

```
Windows monitor + soundcard loopback audio
  -> ffmpeg.exe (ddagrab capture, x264 encode)      start-capture.sh
  -> MediaMTX (local RTMP server)                    rtmp://localhost:1935/desktop
  -> ffmpeg relay (-c copy, no re-encode)             start-x-relay.sh
  -> X ingest                                          rtmps://va.pscp.tv:443/x
```

Capture runs as a *Windows* ffmpeg.exe (needed for `ddagrab` and `dshow`) launched from WSL via interop.
MediaMTX and the relay are Linux processes inside WSL. All files live in `~/mediamtx/`.

## 1. Prerequisites on the new device

| Piece | Where | Notes |
|---|---|---|
| Windows ffmpeg (gpl build, has ddagrab+dshow+libx264) | `winget install yt-dlp.FFmpeg` | Installs under `%LOCALAPPDATA%\Microsoft\WinGet\Packages\yt-dlp.FFmpeg_...\ffmpeg-*-win64-gpl\bin\ffmpeg.exe`. Set `FFEXE` in `start-capture.sh` to that path (WSL form: `/mnt/c/Users/<you>/AppData/Local/...`). |
| Linux ffmpeg + ffprobe inside WSL | `sudo apt install ffmpeg` | Used by the relay and the health checks. 6.1.x is fine. |
| MediaMTX v1.20.1 (linux amd64) | https://github.com/bluenviron/mediamtx/releases/tag/v1.20.1 | `tar xzf` into `~/mediamtx/`. Ships its own `mediamtx.yml`; run it **unmodified** (defaults: RTMP :1935, HLS :8888, RTSP :8554, WebRTC :8889). |
| Audio loopback device | soundcard driver | On WindowsDesktop it is the MOTU M Series `Loopback (MOTU M Series)` DirectShow device. On another box the name will differ, see step 3. |

## 2. Layout

```
~/mediamtx/
  mediamtx, mediamtx.yml     server binary + default config
  start-capture.sh           screen+audio capture, auto-restart loop, writes capture.pid
  start-x-relay.sh           relay to X, auto-reconnect loop
  stream-guard.sh            polls all layers every 20s and self-heals
  capture.pid                PID of the capture wrapper (guard uses kill -0 on it)
  capture.log x-relay.log mediamtx.log   grow ~30MB/evening, rotate between sessions
```

## 3. Device-specific settings to re-check before first run

These were tuned to WindowsDesktop's hardware. Re-measure, do not assume.

1. **Monitor index.** `ddagrab=output_idx=N`. Test each: 
   `ffmpeg.exe -filter_complex "ddagrab=output_idx=1:framerate=30,hwdownload,format=bgra" -t 1 -f null -`
   Currently run with `1`; the guard's `MON_IDX` must match what you launch with.
2. **Audio device name and sample rate.** List devices:
   `ffmpeg.exe -hide_banner -list_devices true -f dshow -i dummy`
   Then test the open with a timeout, it can hang silently at the wrong rate (Gotchas):
   `timeout 20 ffmpeg.exe -f dshow -sample_rate 48000 -channels 2 -i audio="<device>" -t 1 -f null -`
   Set the name and rate in `start-capture.sh`.
3. **Gain.** `volume=3dB,alimiter=limit=0.9:level=disabled` is the music-safe value on the MOTU loopback
   (mean -16 / peak -1.1, no clipping). Mic-only sources wanted ~+12dB. Measure with volumedetect (step 6)
   after any source change. Every gain change needs a capture wrapper restart.
4. **Encoder.** libx264 `superfast`, 1080p30, 6000k. NVENC needs NVIDIA driver >=610; if the new box has
   it, `-c:v h264_nvenc -preset p4 -b:v 6000k` frees the CPU and fixes the headroom issue below.
5. **`FFEXE`** path in `start-capture.sh`.

## 4. Extract the scripts

Save this file as `~/livestreamer.md`, then:

```bash
mkdir -p ~/mediamtx && cd ~/mediamtx
awk '/^<!-- file: /{f=$3; next} /^```/{if(f){if(o){close(f);o=0;f=""}else{o=1}} next} o{print > f}' ~/livestreamer.md
chmod +x start-capture.sh start-x-relay.sh stream-guard.sh && ls -l *.sh
```

Then edit `FFEXE`, the audio device, monitor index, and `X_KEY`.

## 5. Operate

Start everything, order matters, mediamtx first:
```bash
cd ~/mediamtx
setsid nohup ./mediamtx > mediamtx.log 2>&1 < /dev/null &
setsid nohup ./start-capture.sh 1 > capture.log 2>&1 < /dev/null &
setsid nohup ./start-x-relay.sh 'rtmps://va.pscp.tv:443/x' '<STREAM_KEY>' > x-relay.log 2>&1 < /dev/null &
```
Then arm the guard (as a session monitor or `nohup ./stream-guard.sh >> guard.log 2>&1 &`).
Then click **Go Live** in Media Studio Producer once the source shows as receiving.

Restart just capture (the layer that actually dies). **Stop the guard first** or it relaunches capture
while you do and the two wrappers collide on the `desktop` path (continuous rc=187 loop):
```bash
cd ~/mediamtx
kill "$(cat capture.pid)" 2>/dev/null
for p in $(ps -eo pid,args | awk '/bin\/ffmpeg\.exe -hide/{print $1}'); do kill "$p"; done
sleep 2
setsid nohup ./start-capture.sh 1 >> capture.log 2>&1 < /dev/null &
```
~10-15s gap on X. X has held the broadcast through that so far, but it is a grace window, not a guarantee.
Editing `start-capture.sh` does not affect a running wrapper; restart the wrapper, not just its ffmpeg.

Stop everything, guard first, all four layers:
```bash
cd ~/mediamtx
kill "$(cat capture.pid)" 2>/dev/null
for p in $(ps -eo pid,args | awk '/bin\/ffmpeg\.exe -hide/{print $1}'); do kill "$p"; done
for p in $(ps -eo pid,args | awk '/start-x-relay\.sh rtmps/{print $1}'); do kill "$p"; done
pkill -x mediamtx
/mnt/c/Windows/System32/taskkill.exe /F /IM ffmpeg.exe   # belt and braces on the Windows side
rm -f capture.pid
```

## 6. Health checks

```bash
cd ~/mediamtx
ps -eo pid,args | awk '/start-capture\.sh 1$/{print "capture:  " $1}'
ps -eo pid,args | awk '/start-x-relay\.sh rtmps/{print "relay:    " $1}'
pgrep -x mediamtx | sed 's/^/mediamtx: /'
ffprobe -v error -show_entries stream=codec_type,codec_name,width,height,sample_rate -of default=noprint_wrappers=1 rtmp://localhost:1935/desktop
ffmpeg -hide_banner -t 4 -i rtmp://localhost:1935/desktop -map 0:a -af volumedetect -f null - 2>&1 | grep volume
tail -c 500 capture.log | tr '\r' '\n' | grep '^frame=' | tail -1 | grep -o 'speed=[0-9.]*x'
```
Local preview in a Windows browser: http://localhost:8888/desktop. Logs use `\r` progress lines, read
them through `tr '\r' '\n'`.

## 7. Gotchas (all seen for real)

- **dshow open hangs forever at the wrong sample rate.** ffmpeg.exe alive, zero output in `capture.log`
  (not even `Input #0`), relay loops on `no stream is available on path 'desktop'`. The MOTU loopback lists
  44100 but never returns at ffmpeg's default 44.1k; at 48000 or 96000 it opens instantly. Hence
  `-sample_rate 48000 -channels 2`. First test the open directly with a `timeout` before touching anything else.
- **Zombie capture.** ffmpeg.exe stays alive but stops delivering frames (frame counter freezes, no
  warnings). MediaMTX drops the publisher after its 10s `readTimeout`, ffmpeg then logs winsock `-10053`
  and hangs. The guard's freshness check (ffprobe with an 8s timeout, 2 consecutive misses) kills it and the
  wrapper respawns it. ~1 minute gap on X, may need a Go Live re-click.
- ddagrab dies on any display event (fullscreen switch, resolution/HDR change, lock screen, driver reset:
  `AcquireNextFrame failed: 887a0026` = `DXGI_ERROR_ACCESS_LOST`). Not preventable, the wrapper loop recovers in ~5s.
- **WSL interop can fail to launch ffmpeg.exe at all**: bursts of `capture: ffmpeg exited rc=1` with *no
  banner*, preceded by `WSL ... UtilAcceptVsock:271: accept4 failed 110`. Not the encoder, not the device.
  Clears itself after a few loop attempts.
- **Never put `set -e` in a wrapper.** It exits at the ffmpeg line on the first non-zero rc and silently
  disables the watchdog loop. That bug meant capture had never once auto-restarted before 2026-08-21.
- **`pgrep -f` / `pkill -f` match your own shell** (the `bash -c` running the check contains the pattern).
  Inflated counts, and `pkill -f` kills the shell that invoked it. Match precisely with
  `ps -eo pid,args | awk '/start-capture\.sh 1$/'` or kill by PID. The guard checks `capture.pid` with `kill -0` for this reason.
- Only one thing may own capture relaunches at a time: guard or you, never both.
- x264 bitrate is a ceiling, not a pad. A static screen runs far under 6000k. Expected.
- X's player starts muted and runs 15-30s behind. "No audio" is usually the mute button.

## 8. Open issue: encode headroom

Busy content pushes 1080p30 software x264 below realtime (`speed=0.92-0.99x`). Then the dshow buffer
overfills (`real-time buffer ... too full ... frame dropped!`), timestamps go non-monotonic, MediaMTX drops
the relay reader (`DTS is greater than PTS`), and eventually `Conversion failed!` rc=187. Applied
mitigations: `superfast`, `-rtbufsize 256M`, `-af aresample=async=1`. Reduced but not eliminated.
Untested levers with real margin, in order: NVENC if the new GPU/driver allows it; `scale=1280:-2`
(720p, ~half the encode cost); `-fps_mode cfr`; 24fps.

---

## Scripts

<!-- file: start-capture.sh -->
```bash
#!/usr/bin/env bash
# Capture a Windows monitor and push it to the local MediaMTX RTMP server.
# Usage: ./start-capture.sh [monitor_idx]   (default 0; preview at http://localhost:8888/desktop)
# Audio: MOTU M Series hardware loopback = whatever the soundcard is playing.
set -uo pipefail
IDX="${1:-0}"
echo $$ > ~/mediamtx/capture.pid
trap 'rm -f ~/mediamtx/capture.pid' EXIT
FFEXE="/mnt/c/Users/tunas/AppData/Local/Microsoft/WinGet/Packages/yt-dlp.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-N-125365-g9a01c1cb6a-win64-gpl/bin/ffmpeg.exe"

# Watchdog loop: ddagrab dies on any display event (DXGI ACCESS_LOST 0x887a0026 —
# fullscreen switch, resolution/HDR change, lock screen, driver reset) and cannot
# re-acquire in-process. Restarting re-acquires the duplication session cleanly.
while true; do
  echo "[$(date '+%F %T')] capture: starting (monitor ${IDX})"
  "$FFEXE" -hide_banner \
    -filter_complex "ddagrab=output_idx=${IDX}:framerate=30,hwdownload,format=bgra,scale=1920:-2,format=yuv420p" \
    -f dshow -sample_rate 48000 -channels 2 -audio_buffer_size 50 -rtbufsize 256M -i audio="Loopback (MOTU M Series)" \
    -c:v libx264 -preset superfast -b:v 6000k -maxrate 6000k -bufsize 12000k -g 60 \
    -c:a aac -b:a 128k -af aresample=async=1,volume=3dB,alimiter=limit=0.9:level=disabled \
    -f flv rtmp://localhost:1935/desktop
  rc=$?
  echo "[$(date '+%F %T')] capture: ffmpeg exited rc=${rc}; restarting in 3s"
  sleep 3
done
```

<!-- file: start-x-relay.sh -->
```bash
#!/usr/bin/env bash
# Relay the local desktop stream to X Live. No re-encode — pure copy.
# Usage: ./start-x-relay.sh '<rtmp(s)-ingest-url-from-media-studio>' '<stream-key>'
# Get both from X Media Studio -> Producer -> Sources (media.x.com), NOT the developer portal.
#
# Auto-reconnect: if the push to X drops (network blip, X-side reset), retry
# every RETRY_SECS while the local stream is still publishing. This resumes the
# broadcast only within X's reconnect grace window — if X fully ends the
# broadcast, the source goes hot again but "Go Live" must be clicked by hand.
set -uo pipefail
[ $# -eq 2 ] || { echo "usage: $0 <ingest-url> <stream-key>" >&2; exit 1; }
URL="${1%/}"; KEY="$2"
RETRY_SECS=5

while true; do
  echo "[$(date '+%F %T')] relay: connecting to ${URL}/<key>"
  ffmpeg -hide_banner \
    -i rtmp://localhost:1935/desktop \
    -c copy \
    -f flv "${URL}/${KEY}"
  rc=$?
  echo "[$(date '+%F %T')] relay: ffmpeg exited rc=${rc}; retrying in ${RETRY_SECS}s"
  sleep "${RETRY_SECS}"
done
```

<!-- file: stream-guard.sh -->
```bash
#!/usr/bin/env bash
# Stream guard: polls the X-live chain every INTERVAL seconds and repairs it.
# stdout = action/alert lines only (consumed by a session Monitor); healthy polls are silent.
# Layers guarded: mediamtx server, capture wrapper (start-capture.sh), relay wrapper
# (start-x-relay.sh), and stream freshness (catches zombie ffmpeg.exe that holds the
# process slot but publishes nothing — seen 2026-08-19).
set -u
INTERVAL=20
MON_IDX=1
X_URL='rtmps://va.pscp.tv:443/x'
X_KEY='<STREAM_KEY>'
FAILS=0

ts() { date '+%F %T'; }

while true; do
  # 1) mediamtx server
  if ! pgrep -x mediamtx >/dev/null; then
    echo "[$(ts)] GUARD: mediamtx down — restarting"
    (cd ~/mediamtx && nohup ./mediamtx >> mediamtx.log 2>&1 &)
    sleep 3
  fi

  # 2) capture wrapper loop
  if ! kill -0 "$(cat ~/mediamtx/capture.pid 2>/dev/null)" 2>/dev/null; then
    echo "[$(ts)] GUARD: capture wrapper gone — relaunching (monitor ${MON_IDX})"
    nohup ~/mediamtx/start-capture.sh "${MON_IDX}" >> ~/mediamtx/capture.log 2>&1 &
    sleep 5
  fi

  # 3) relay wrapper loop
  if ! pgrep -f "start-x" >/dev/null; then
    echo "[$(ts)] GUARD: relay wrapper gone — relaunching"
    nohup ~/mediamtx/start-x-relay.sh "${X_URL}" "${X_KEY}" >> ~/mediamtx/x-relay.log 2>&1 &
  fi

  # 4) stream freshness (zombie detection): must deliver packets within 8s
  if timeout 8 ffprobe -v error -show_entries stream=codec_type -of csv=p=0 \
      rtmp://localhost:1935/desktop >/dev/null 2>&1; then
    FAILS=0
  else
    FAILS=$((FAILS+1))
    if [ "$FAILS" -ge 2 ]; then
      echo "[$(ts)] GUARD: local stream stale x${FAILS} — killing capture ffmpeg (wrapper restarts it)"
      pkill -f "ffmpeg[.]exe"
      FAILS=0
    fi
  fi

  sleep "${INTERVAL}"
done
```
