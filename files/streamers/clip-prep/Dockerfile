# clip-prep:0.1 — #282. ffmpeg + a stdlib HTTP server; the StreamerBrain PG's MP4 → wav + frames step.
# Streamers demo track, runs on spark-dd06's k3s. Multi-arch base; build natively on the box:
#   sg docker -c "docker build -t clip-prep:0.1 files/streamers/clip-prep"
# k3s uses its own containerd, not Docker, so then (needs sudo):
#   sudo bash -c 'docker save clip-prep:0.1 | k3s ctr images import -'
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*
COPY server.py /server.py
EXPOSE 8090
CMD ["python3", "/server.py"]
