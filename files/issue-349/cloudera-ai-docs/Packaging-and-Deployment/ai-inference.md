# Cloudera AI Inference service Overview

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/

Product: machine-learning 1.5.5

## [Cloudera AI Inference service Overview](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-use-caii.html)

Cloudera AI Inference service provides a production-grade serving environment for hosting predictive and generative AI. It is designed to handle the challenges of production deployments, such as high availability, performance, fault tolerance, and scalability. The Cloudera AI Inference service allows data scientists and machine learning engineers to deploy their models quickly, without worrying about the infrastructure and maintenance. Cloudera AI Inference service supports running 100 or more model endpoints simultaneously, provided that the underlying compute resources are adequately and correctly sized.

### [Key features for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-key-features.html)

The key features of Cloudera AI Inference service includes:

### [Multiple Cloudera AI Registries connected to a single Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-multiple-cloudera-ai-registries-to-single-cloudera-ai-inference.html)

Cloudera supports deploying Cloudera AI Inference service connecting to multiple Cloudera AI Registries in Cloudera AI 1.5.5 SP3 and higher releases.

### [Key applications for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-key-applications.html)

Large Language Models deployed on Cloudera AI Inference service with NVIDIA NIM enable the following applications:

### [Terminology for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-glossary-terms-terminology.html)

Get familiar with the Cloudera AI Inference service terminology and usage.

### [Limitations and restrictions for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-limitations-restriction.html)

Consider the listed limitations and restrictions when using Cloudera AI Inference service.

### [Supported model artifact formats for Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-supported-model-artifact-formats.html)

Lists Cloudera AI Inference service supported models:

## [Cloudera AI Inference service concepts](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-caii-concepts.html)

Learn the following Cloudera AI Inference service concepts before setting up the Cloudera AI Inference service.

## [Authenticating Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-authentication.html)

Cloudera AI Inference service secures all incoming requests to application and model endpoints using Cloudera Workload Authentication. Users and client applications must authenticate using one of the supported token- or key-based mechanisms before gaining access to HTTP endpoints.

### [Authenticating Cloudera AI Inference service using CDP token](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-authenticating-cloudera-ai-inference-service.html)

Cloudera AI Inference service can use a CDP_TOKEN obtained from the User Management Service (UMS) to authenticate users and clients that interact with all HTTP endpoints exposed by the service workload.

### [Authenticating Cloudera AI Inference service with Knox API keys](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-prerequisites-using-api-key.html)

To enable using API keys, you must manually configure the Knox service in the Cloudera Base cluster. This includes installing and configuring Knox and setting up the Cloudera AI Inference service instance in the Cloudera AI Control Plane.

## [Managing Model Endpoints using UI](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-manage-endpoints-use-ui.html)

Cloudera AI Inference service lets you deploy models saved in the Cloudera AI Registry.

### [Creating a Model Endpoint using UI](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-create-model-endpoint-ui.html)

Select a specific Cloudera AI Inference service instance and a model version from Cloudera AI Registry to create a new model endpoint.

### [Listing Model Endpoints using UI](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-list-model-endpoints-ui.html)

The Model Endpoints landing page displays a table view that represents a comprehensive list of all the model endpoints across the running Cloudera AI Inference service instances in your Cloudera account.

### [Viewing details of a Model Endpoint using UI](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-view-details-model-endpoint.html)

You can view the information of a Model Endpoint, edit its configuration, view metric charts on resource utilization, and so on.

### [Authenticating with Model Endpoints using UI](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-authenticate-model-endpoint.html)

You can generate credentials to authenticate application requests or test model endpoints directly from the Model Endpoint Details page in the Cloudera AI console. Using the Generate Key / Token menu, you can obtain Knox API keys or short-lived JWT tokens without leaving the interface.

### [Editing a Model Endpoint Configuration using UI](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-edit-model-endpoint-configuration-ui.html)

You can edit the configuration of a specific model endpoint for resources or select model versions.

## [Managing Model Endpoints using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-manage-endpoints-using-api.html)

You can use API to create, view, list, edit, describe, and delete model endpoints.

### [Preparing to interact with the Cloudera AI Inference service API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-prepare-interact-caii-api.html)

To interact with Cloudera AI Inference service API, you need to obtain the domain name of the Cloudera AI Inference service and your Cloudera JSON Web Token (JWT) and save it as environment variables.

### [Creating a Model Endpoint using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-create-model-endpoint-api.html)

You can select a specific Cloudera AI Inference service instance and a model version from Cloudera AI Registry to create a new model endpoint.

### [Listing Model Endpoints using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-list-model-endpoints-api.html)

Consider the following details for listing Model Endpoints using API.

### [Describing a Model Endpoint using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-describe-model-endpoint-use-api.html)

Consider the instructions for describing a Model Endpoint using API.

### [Deleting a Model Endpoint using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-delete-model-endpoint-api.html)

Consider the following instruction to delete a Model Endpoint using API.

### [Autoscaling Model Endpoints using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-autoscale-model-endpoint.html)

You can configure the Model Endpoints deployed on Cloudera AI Inference service to auto-scale to zero instances when there is no load.

### [Tuning autoscaling sensitivity using the API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-tuning-auto-scale-sensitivity-use-api.html)

To customize the autoscaling sensitivity and requisites, set the target and metric fields in the autoscaling.autoscalingconfig parameter.

### [Running Models on GPU](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-run-models-gpu.html)

Follow the guidelines for running Models on GPU.

### [Deploying models with Canary deployment using API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-deploy-models-canary-deployment-use-api.html)

Cloudera AI Inference service allows users to control traffic percentage to specific model deployments.

## [Interacting with Model Endpoints](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-interact-endpoints.html)

You can interact with the Cloudera AI Inference service API using an HTTP/REST client, such as cURL.

### [Making an inference call to a Model Endpoint with an OpenAI API](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-make-inference-call-model-endpoint-with-openai-api.html)

Language models for text generation are deployed using NVIDIA’s NIM microservices. These model endpoints are compliant with the OpenAI Protocol. See NVIDIA NIM documentation for supported OpenAI APIs and NVIDIA NIM specific extensions such as Function Calling and Structured Generation.

- [Cloudera AI Inference service using OpenAI Python SDK client in a Cloudera AI Workbench Session](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-inference-using-openai-phython-sdk-session.html): Consider the following instructions on interacting with an instruction-tuned large language model endpoint hosted on Cloudera AI Inference service.
- [Cloudera AI Inference service using OpenAI Python SDK client on a local machine](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-inference-using-openai-phython-sdk-local-machine.html): Consider the following guidelines for Cloudera AI Inference service using OpenAI Python SDK client.
- [OpenAI Inference Protocol Using Curl](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-openai-inference-protocol-using-curl.html): Consider this example for OpenAI Inference Protocol Using Curl.

### [Making an inference call to a Model Endpoint with Open Inference Protocol](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-make-inference-call-model-endpoint-with-open-Inference-protocol.html)

Cloudera AI Inference service serves predictive ONNX models using the NVIDIA Triton Server. The deployed model endpoints are compliant with Open Inference Protocol version 2.

- [Open Inference Protocol Using Python SDK](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-open-inference-protocol-using-python-sdk.html): Use the following code sample to interact with a model endpoint using the Open Inference Protocol.
- [Open Inference Protocol Using Curl](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-open-inference-protocol-using-curl.html): Consider the following instructions for using Open Interference Protocol Using Curl.

## [Deploying Predictive Models](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-deploy-predictive-models.html)

The following example illustrates how to train a model on a Cloudera AI workbench, register it, and then deploy it to Cloudera AI Inference.

## [Accessing Cloudera AI Inference service Metrics](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-caii-access-caii-service-metrics.html)

Cloudera AI Inference service exposes Prometheus metrics for the deployed Model Endpoints. The UI displays plots of a few chosen metrics for each model endpoint.

## [Grafana dashboards for Cloudera AI Inference](https://docs.cloudera.com/machine-learning/1.5.5/ai-inference/topics/ml-enhanced-grafana-monitoring-cloudera-ai-inference.html)

Cloudera AI Inference service provides dedicated Grafana dashboards that expose model-serving infrastructure metrics. These dashboards offer observability with Cloudera AI Inference service views and expanded metric coverage, enabling easier monitoring and troubleshooting of the Cloudera AI Inference service deployment.

