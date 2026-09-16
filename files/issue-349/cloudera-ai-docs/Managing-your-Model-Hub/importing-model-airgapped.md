# Downloading and uploading Model Repositories for an air-gapped environment

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/

Product: machine-learning 1.5.5

## [Downloading and uploading Model Repositories for an air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-models-in-air-gapped-environment.html)

An air-gapped environment is physically isolated from the internet and external networks, preventing the transmission or reception of data online. As a result, enabling the download of Model Repositories in such environments requires the Administrator to perform additional steps.

### [Prerequisites for downloading and uploading Model artifacts in air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-prerequisites-downloading-uploading-models-air-gapped.html)

Before downloading or uploading models, ensure you have the following tools and configurations installed on the host that is connected to the airgap setup. This might be your bastion host.

### [Configuring model import script in air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-configuring-model-import-air-gapped-environment.html)

To configure the model import utility in air-gapped environment, run the import_to_airgap.py script with the --configure flag.

### [Understanding NVIDIA NGC file](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-understanding-nvidia-ngc-file-airgap.html)

The NGC specification script includes commands to iterate through the NGC specification file and retrieve the repository ID.

### [Downloading model repositories for an air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-downloading-model-repositories-air-gapped.html)

To use models from Hugging Face and NVIDIA NGC (NIM), the Administrator must download model artifacts from these sources on specially networked hosts, bastion hosts.

### [Uploading Model Repositories for an air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-uploading-model-repositories-air-gapped.html)

The Model artifacts must be manually transferred and uploaded to the object storage utilized by the Cloudera AI Registry and Cloudera AI Inference service.

### [Creating the Model entry in Cloudera AI Registry in air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-creating-model-entry-ai-registry-air-gapped.html)

The example outlines how to create the Model entry in Cloudera AI Registry within an air-gapped environment.

### [Importing Model to Cloudera AI Registry in air-gapped environment](https://docs.cloudera.com/machine-learning/1.5.5/importing-model-airgapped/topics/ml-importing-model-ai-registry-air-gapped.html)

You can import the Hugging Face models listed on the Model Hub page into your Cloudera AI Registry.

