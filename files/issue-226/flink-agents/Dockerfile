# spark-flink-agents:0.3.1-kafka — the aarch64 build for NvidiaSpark-1 (spark-dd06), k3s-cso §8.
#
# Byte-for-byte the cso-prod-1 recipe (files/cso-prod-1/flink-agents/Dockerfile, #231) — it needed
# NO aarch64 changes. Both base images (maven:3-eclipse-temurin-17, flink:1.20.5-java17) are
# multi-arch, and everything else is built from source or installed from PyPI sdists/wheels that
# publish aarch64. Build with `docker build --platform linux/arm64`.
#
# The `-kafka` tag adds two things on top of the proven 0.3.1 image, both for the Agentic-Studio
# Kafka pipeline (#231, plan §7 Phase 4): the flink-sql-connector-kafka jar on /opt/flink/lib
# (KafkaSource/KafkaSink need it), and the repointed/new agent scripts baked in so the image is
# self-contained. Nothing else changed from 0.3.1.
#
# k3s-cso §8's CUDA-wheel table does NOT apply here: that is the separate GPU-PyTorch Flink image
# (the v5 recipe). flink-agents talks to the LLM over HTTP, so this image needs no CUDA at all —
# the GPU claim is proven by the stock-image FlinkDeployment in files/issue-226/flink-gpu.yaml.
#
# k3s uses its own containerd, not Docker, so after building:
#   sudo bash -c 'docker save spark-flink-agents:0.3.1-kafka | k3s ctr images import -'

# ---- Stage 1: build flink-agents from source (Maven jars + Python wheel) ----
FROM maven:3-eclipse-temurin-17 AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        git python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone --depth 1 --branch release-0.3.1 https://github.com/apache/flink-agents.git

WORKDIR /src/flink-agents

# Java build (same as tools/build.sh --java): produces
#   dist/common/target/flink-agents-dist-common-0.3.1.jar
#   dist/flink-*/target/flink-agents-dist-flink-*-0.3.1-thin.jar
RUN mvn clean install -DskipTests -B -Dspotless.skip=true

# Python wheel build, replicating tools/build.sh's python leg without uv:
# copy the dist jars into python/flink_agents/lib (bundled into the wheel as
# package data), then build the wheel -> python/dist/flink_agents-0.3.1-*.whl
RUN set -eux; \
    LIB=python/flink_agents/lib; \
    rm -rf "$LIB"; mkdir -p "$LIB/common"; \
    cp dist/common/target/flink-agents-dist-common-*.jar "$LIB/common/"; \
    for d in dist/flink-*; do \
        v=$(basename "$d"); mkdir -p "$LIB/$v"; \
        cp "$d"/target/flink-agents-dist-"$v"-*-thin.jar "$LIB/$v/"; \
    done; \
    python3 -m venv /buildvenv; \
    /buildvenv/bin/pip install --no-cache-dir build; \
    cd python && /buildvenv/bin/python -m build --wheel

# ---- Stage 2: runtime image ----
FROM flink:1.20.5-java17

USER root

# Python 3.11 (flink-agents supports 3.10/3.11; 3.12 needs Flink >= 2.1).
# curl + ca-certificates are added for the Kafka connector fetch below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev build-essential \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Isolated site-packages for the agents runtime: apache-flink (pyflink) pulls
# numpy, pyarrow, apache-beam, pemja; kafka-python per the Ratatoskr dep list;
# then the flink-agents wheel built in stage 1.
COPY --from=build /src/flink-agents/python/dist/*.whl /tmp/wheels/
RUN python3.11 -m venv /opt/flink/agents-venv \
    && /opt/flink/agents-venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/flink/agents-venv/bin/pip install --no-cache-dir \
        apache-flink==1.20.5 kafka-python /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels

# Jars: flink-agents dist (common + flink-1.20 thin) and the bundled
# flink-python jar into /opt/flink/lib so PythonDriver is on the classpath.
COPY --from=build /src/flink-agents/dist/common/target/flink-agents-dist-common-*.jar /opt/flink/lib/
COPY --from=build /src/flink-agents/dist/flink-1.20/target/flink-agents-dist-flink-1.20-*-thin.jar /opt/flink/lib/
RUN cp /opt/flink/opt/flink-python-*.jar /opt/flink/lib/

# Kafka connector for the Agentic-Studio pipeline (#231): KafkaSource/KafkaSink
# resolve only if this fat "sql-connector" jar (bundles the kafka client) is on
# the cluster classpath. Pinned to the Flink 1.20 line.
ARG KAFKA_CONNECTOR=3.4.0-1.20
RUN curl -fsSL -o /opt/flink/lib/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar \
        "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/${KAFKA_CONNECTOR}/flink-sql-connector-kafka-${KAFKA_CONNECTOR}.jar"

# Example agent jobs (the full flink_agents.examples package is also installed
# in the venv via the wheel; these are the submittable entry scripts).
RUN mkdir -p /opt/flink/usrlib/agents
COPY --from=build /src/flink-agents/python/flink_agents/examples/quickstart/*.py /opt/flink/usrlib/agents/
# The examples resolve their input as <script dir>/resources/... (FileSource),
# so the resources dir has to sit next to the scripts, on JM and TM alike.
COPY --from=build /src/flink-agents/python/flink_agents/examples/quickstart/resources /opt/flink/usrlib/agents/resources

# The repointed/new agent scripts (from this build context), baked in so the
# image is self-contained — no kubectl cp needed on each pod restart.
# vllm_review_agent.py rides to the TMs via `flink run -pyfs`; the two job
# scripts are the -py entry points (file-based regression + Kafka pipeline).
COPY vllm_review_agent.py workflow_agent_vllm_example.py kafka_agent_job.py /opt/flink/usrlib/agents/

# Make the venv python the default python for PyFlink (driver + workers).
ENV PYFLINK_CLIENT_EXECUTABLE=/opt/flink/agents-venv/bin/python
# flink-agents runs the Python UDF in pemja thread mode (embedded libpython),
# which does not pick up the venv on its own -> expose the site-packages.
ENV PYTHONPATH=/opt/flink/agents-venv/lib/python3.11/site-packages
RUN ln -sf /opt/flink/agents-venv/bin/python /usr/local/bin/python \
    && chown -R flink:flink /opt/flink/agents-venv /opt/flink/usrlib

USER flink
