# cso-operator-flink-agents:0.3.1
# Multi-stage source build of Apache Flink Agents 0.3.1 onto flink:1.20.5-java17.
# Per DesktopShare/flink-agents-cso-plan.md §4.6. Built into the cso-prod-1
# minikube docker daemon (eval $(minikube -p cso-prod-1 docker-env)).

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

# Python 3.11 (flink-agents supports 3.10/3.11; 3.12 needs Flink >= 2.1)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev build-essential \
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

# Example agent jobs (the full flink_agents.examples package is also installed
# in the venv via the wheel; these are the submittable entry scripts).
RUN mkdir -p /opt/flink/usrlib/agents
COPY --from=build /src/flink-agents/python/flink_agents/examples/quickstart/*.py /opt/flink/usrlib/agents/
# The examples resolve their input as <script dir>/resources/... (FileSource),
# so the resources dir has to sit next to the scripts, on JM and TM alike.
COPY --from=build /src/flink-agents/python/flink_agents/examples/quickstart/resources /opt/flink/usrlib/agents/resources

# Make the venv python the default python for PyFlink (driver + workers).
ENV PYFLINK_CLIENT_EXECUTABLE=/opt/flink/agents-venv/bin/python
# flink-agents runs the Python UDF in pemja thread mode (embedded libpython),
# which does not pick up the venv on its own -> expose the site-packages.
ENV PYTHONPATH=/opt/flink/agents-venv/lib/python3.11/site-packages
RUN ln -sf /opt/flink/agents-venv/bin/python /usr/local/bin/python \
    && chown -R flink:flink /opt/flink/agents-venv /opt/flink/usrlib

USER flink
