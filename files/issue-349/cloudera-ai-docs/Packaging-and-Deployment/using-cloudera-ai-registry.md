# Using Cloudera AI Registry

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/

Product: machine-learning 1.5.5

## [Using Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-using-model-registry.html)

Cloudera AI Registry is the core enabler for MLOps, or DevOps for machine learning.

### [Cloudera AI Registry standalone API](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-registry-standalone-api.html)

You can use the standalone Cloudera AI Registry API to communicate with the Cloudera AI Registry using the REST client or CLI client.

- [Authenticating clients for interacting with Cloudera AI Registry API](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-registry-standalone-api-authentication.html): Clients that interact with the Cloudera AI Registry Standalone API and with model endpoints must obtain a JSON Web Token (JWT) from the Cloudera control plane, which must be passed as a Bearer token in HTTP requests sent to the serving API and endpoints.
- [Role-based authorization](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-registry-standalone-api-authorization.html): Cloudera AI Registry implements role-based access control.
- [Multiple Cloudera AI Registries connected to a single Cloudera AI Inference service](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-multiple-cloudera-ai-registries-to-single-cloudera-ai-inference.html): Cloudera supports deploying Cloudera AI Inference service connecting to multiple Cloudera AI Registries in Cloudera AI 1.5.5 SP3 and higher releases.
- [Using the REST Client](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-registry-standalone-api-rest-client.html): You need the domain information to use the REST client to interact with the registry.
- [Troubleshooting issues with Cloudera AI Registry API](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-registry-standalone-api-troublshooting.html): Learn about some of the recommended series of steps to perform when troubleshooting issues related to the Cloudera AI Registry API.
  - [Debugging the model import failure](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-registry-standalone-api-troubleshoot-debug-model-import-failure.html): To debug errors that occurred on the Cloudera AI Registry server, you can access the logs found in the API v2 pod.

## [Importing a Hugging Face Model (Technical Preview)](https://docs.cloudera.com/machine-learning/1.5.5/using-cloudera-ai-registry/topics/ml-import-huggingface-model-from-registered-models.html)

If your desired Hugging Face model is unavailable on the Model Hub page, you can import those models from the Hugging Face website. After you import the model, the newly imported model will be listed on the Registered Models page.

