# Official Cloudera Flink base (RHEL/UBI variant)
FROM container.repository.cloudera.com/cloudera/flink:1.20.1-csaop1.5.0-b275

USER root

# 1. HEAVY LAYER: Cached PyTorch download (approx 5GB)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 2. SYSTEM LAYER: Adding 'tar' for kubectl cp and 'find' to locate jars
RUN microdnf update -y && \
    microdnf install -y wget mesa-libGL glib2 libXrender libXext shadow-utils tar findutils && \
    microdnf clean all

# 3. FLINK PYTHON CONNECTOR: Move the optional jar to the active lib folder
# This fixes the 'flink-python module seems to be missing' error
RUN cp /opt/flink/opt/flink-python*.jar /opt/flink/lib/

# 4. RUNTIME LAYER: NVIDIA Python runtime wheels
RUN pip install --no-cache-dir \
    nvidia-cuda-runtime-cu12 \
    nvidia-cudnn-cu12 \
    nvidia-cublas-cu12

# 5. CONFIG & PATHS: The "Secret Sauce" for CUDA discovery
RUN mkdir -p /opt/flink/conf && touch /opt/flink/conf/flink-conf.yaml && \
    export SITE_PACKAGES=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    echo "$SITE_PACKAGES/nvidia/cuda_runtime/lib" > /etc/ld.so.conf.d/nvidia-pip.conf && \
    echo "$SITE_PACKAGES/nvidia/cudnn/lib" >> /etc/ld.so.conf.d/nvidia-pip.conf && \
    ldconfig

ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:${LD_LIBRARY_PATH}
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

USER flink
ENTRYPOINT ["python3", "-c", "import torch; print('CUDA Available:', torch.cuda.is_available()); print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"]
