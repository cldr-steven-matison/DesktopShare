# Setting up Cloudera AI Registry

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/

Product: machine-learning 1.5.5

## [Setting up Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-setting-up-model-registry.html)

Cloudera AI Registry is the core enabler for MLOps, or DevOps for machine learning.

### [Prerequisites for creating Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-creating-model-registry-ozone-configuration-pvc.html)

Cloudera AI Registry on premises uses Apache Ozone to store model artifacts in Cloudera AI on premises 1.5.5 and S3 compatible object storage to store model artifacts in Cloudera AI on premises 1.5.5 SP1 and higher releases. Before creating Cloudera AI Registry in Cloudera AI on premises 1.5.5 SP1 and higher releases, make sure you have the S3 compatible object storage credentials.Cloudera AI Registry also requires dedicated TLS certificates as it operates through a separate Istio gateway, which does not support shared certificates.

### [Creating a Cloudera AI Registry with the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-creating-model-registry.html)

Before you can start using Cloudera AI Registry you must create a Cloudera AI Registry for your environment.

### [Creating a Cloudera AI Registry with CDP CLI](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-creating-ai-registry-cdp-cli.html)

Before you can start using Cloudera AI Registry you must create a Cloudera AI Registry for your environment. You can create Cloudera AI Registry with CDP CLI.

### [Refreshing Cloudera AI Registry using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-refreshing-cloudera-ai-registry-using-ui.html)

Refresh the Cloudera AI Registry instance to synchronize the latest certificates from the Cloudera console with the deployments that rely on these certificates within Cloudera AI Registry service. This feature is available from Cloudera AI on premises 1.5.5 SP1.

### [Refreshing Cloudera AI Registry using the CLI](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-refreshing-cloudera-ai-registry-using-cli.html)

Refresh the Cloudera AI Registry instance to synchronize the latest certificates from the Cloudera console with the deployments that rely on these certificates within Cloudera AI Registry service. This feature is available from Cloudera AI on premises 1.5.5 SP1.

### [Setting up certificates for Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-cai-registry-setting-up-certificates.html)

Cloudera AI Registry requires its own dedicated TLS certificate as it operates through a separate Istio gateway that does not support shared certificates.

### [Synchronizing Cloudera AI Registry with a workbench](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-synchronizing-model-registry-with-workspace.html)

If you deploy a Cloudera AI Registry in an environment that contains one or more Cloudera AI Workbench, you must synchronize Cloudera AI Registry with the workbenches.

### [Viewing details for Cloudera AI Registries](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-viewing-registered-model-information.html)

You can view the information for your registered models using AI Registries.

### [Cloudera AI Registry permissions](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-model-registry-permissions.html)

Cloudera AI Registry's permissions for the following actions are separate from workbench permissions, but they are inherited from environment level workbench permissions.

### [Model access control](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-model-registry-model-access-control.html)

Access to models is dependent on the user permissions.

### [Diagnostic bundle support for Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-cloudera-ai-registry-diagnostic-bundle-support.html)

Collecting a diagnostic bundle from the Cloudera Management Console provides a comprehensive snapshot of the system by gathering two types of logs.

### [Prerequisites for Cloudera AI Registry standalone API](https://docs.cloudera.com/machine-learning/1.5.5/setup-model-registry/topics/ml-registry-standalone-api-prereqs.html)

To set up the Cloudera AI Registry standalone API, configure the Cloudera AI Inference service and import pretrained Models.

