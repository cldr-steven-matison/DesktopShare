# Cloudera AI Inference service Overview

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/

Product: machine-learning 1.5.5

## [Cloudera AI Inference service Overview](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-use-caii.html)

Cloudera AI Inference service provides a production-grade serving environment for hosting predictive and generative AI. It is designed to handle the challenges of production deployments, such as high availability, performance, fault tolerance, and scalability. The Cloudera AI Inference service allows data scientists and machine learning engineers to deploy their models quickly, without worrying about the infrastructure and maintenance. Cloudera AI Inference service supports running 100 or more model endpoints simultaneously, provided that the underlying compute resources are adequately and correctly sized.

### [Key features for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-key-features.html)

The key features of Cloudera AI Inference service includes:

### [Key applications for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-key-applications.html)

Large Language Models deployed on Cloudera AI Inference service with NVIDIA NIM enable the following applications:

### [Terminology for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-glossary-terms-terminology.html)

Get familiar with the Cloudera AI Inference service terminology and usage.

### [Limitations and restrictions for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-limitations-restriction.html)

Consider the listed limitations and restrictions when using Cloudera AI Inference service.

### [Supported model artifact formats for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-supported-model-artifact-formats.html)

Lists Cloudera AI Inference service supported models:

## [Authorization of Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-authorization.html)

Cloudera AI Inference service implements role-based access control.

### [Assigning Cloudera AI Inference service level administrator and user roles](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-assigning-caii-administrator-user-roles.html)

You can manage access to an Cloudera AI Inference service instance by assigning users either the Administrator or the User role.

### [Prerequisites for configuring Fine-grained authorization](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-prerequisites-configuring-fine-grained-authorization.html)

To use Fine-grained authorization, you must manually configure the Ranger and RAZ services in the Base Cluster. This includes installing and configuring both services and setting up the Cloudera AI Inference service instance in the Cloudera AI Control Plane.

### [Configuring fine-grained access control for Model Endpoints](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-fine-grain-access.html)

Fine-grained access control allows Administrators to define specific access levels for Model Endpoints for individual users or groups.

## [Non-transparent proxy support on Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-ntp-support-cai.html)

Proxy support in Cloudera AI Inference service, available in Cloudera AI on premises 1.5.5 SP2 and higher releases, addresses the critical need for secure and compliant outbound traffic management within air-gapped or heavily restricted network environments. This feature ensures that all outbound network traffic originating from the Cloudera AI Inference service data plane is routed exclusively through the configured proxy.

## [Cloudera AI Inference service Configuration and Sizing](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-caii-configuration-sizing.html)

Consider the following factors for the configuration and sizing of Cloudera AI Inference service.

## [Prerequisites for setting up Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-prerequisites-set-up.html)

Several prerequisites must be considered before setting up Cloudera AI Inference service.

### [Importing Models](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-import-nvidia-nim-llm.html)

Model Hub offers a curated list of top-performing models from the NVIDIA NGC Catalog and Hugging Face.

### [Register an ONNX model to Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-register-onnx-model-model-registry.html)

Register your ONNX model to Cloudera AI Registry.

## [Managing Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-manage-endpoints.html)

Cloudera AI Inference service provides an UI and CLI interface to manage the life cycle of the service and associated infrastructure.

### [Managing Cloudera AI Inference service using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-manage-instance-ui.html)

You can manage the life cycle of the Cloudera AI Inference service and associated infrastructure using the UI.

- [Creating a Cloudera AI Inference service instance using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-create-instance-ui.html): You can create a Cloudera AI Inference service instance using the UI.
- [Listing Cloudera AI Inference service instances using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-list-instance-ui.html): You can view the list of all the Cloudera AI Inference service instances in your cluster. It provides details like the name of the Cloudera AI Inference service, status, associated environment name, created date and time.
- [Viewing details of a Cloudera AI Inference service instances using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-describe-instance-ui.html): You can view detailed configuration information about a specific Cloudera AI Inference service instance. .
- [Refreshing Cloudera AI Inference service using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-refreshing-cloudera-ai-inference-service.html): The Cloudera AI Inference service relies on a complex certificate trust chain across multiple Kubernetes namespaces, in Cloudera AI on premises. 1.5.5 SP1 and higher releases.
- [Updating Cloudera AI Inference service instance using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-updating-cloudera-ai-inference-service-instance-ui.html): Update the S3 credentials, S3 endpoint details and the S3 region information using the UI. This feature is available from Cloudera AI on premises 1.5.5 SP1.
- [Deleting Cloudera AI Inference service instances using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-delete-instance-ui.html): You can delete a Cloudera AI Inference service instance if it is no longer needed.
- [Obtaining Control plane audit logs for Cloudera AI Inference service using the UI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-obtain-log-instance-ui.html): You can obtain Control plane audit logs for Cloudera AI Inference service. You can use the audit log entries and the logs for troubleshooting purposes.

### [Managing Cloudera AI Inference service using CDP CLI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-manage-endpoints-use-cdp-cli.html)

Cloudera AI Inference service provides a CLI interface to manage the life cycle of the service and associated infrastructure.

- [Creating a Cloudera AI Inference service instance](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-create-caii-instance.html): Cloudera recommends creating a Cloudera AI Inference service by first generating the CLI input skeleton, customizing the JSON file, and then passing the file to the creation command.
- [Listing Cloudera AI Inference service instances](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-list-instances.html): You can list the Cloudera AI Inference service instances in your Cloudera tenant with the help of a command.
- [Describing Cloudera AI Inference service instance](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-describe-caii-instance.html): The describe command shows you all the detailed configuration information about a specific Cloudera AI Inference service.
- [Refreshing Cloudera AI Inference service using the CLI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-refreshing-cloudera-ai-inference-service-using-cli.html): The Cloudera AI Inference service relies on a complex certificate trust chain across multiple Kubernetes namespaces in Cloudera AI on premises. Refresh the Cloudera AI Inference service instance to upload the certificate and to refresh the Cloudera AI Inference service deployment to support TLS. This feature is available from Cloudera AI on premises 1.5.5 SP1.
- [Updating Cloudera AI Inference instance using Cloudera CLI](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-updating-cloudera-ai-inference-instance-cli.html): Update the S3 credentials, S3 endpoint details and the S3 region information using the Cloudera CLI. This feature is available in Cloudera AI on premises 1.5.5 SP1 and higher releases.
- [Deleting Cloudera AI Inference service instance](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-delete-caii-instance.html): Consider the following instructions for deleting a Cloudera AI Inference service instance.

## [Setting up certificates for Cloudera AI Inference Service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-setting-up-certificates.html)

Cloudera AI Inference service requires its own dedicated TLS certificate as it operates through a separate Istio gateway that does not support shared certificates.

## [Grafana dashboards for Cloudera AI Inference](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-enhanced-grafana-monitoring-cloudera-ai-inference.html)

Cloudera AI Inference service provides dedicated Grafana dashboards that expose model-serving infrastructure metrics. These dashboards offer observability with Cloudera AI Inference service views and expanded metric coverage, enabling easier monitoring and troubleshooting of the Cloudera AI Inference service deployment.

## [Diagnostic bundle support for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/setup-cloudera-ai-inference/topics/ml-caii-diagnostic-bundle-support-caii.html)

Collecting a diagnostic bundle from the Cloudera Management Console provides a comprehensive snapshot of the system by gathering two types of logs.

