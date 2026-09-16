# Experiments with MLflow

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/experiments/

Product: machine-learning 1.5.5

## [Experiments with MLflow](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-experiments-v2.html)

Machine Learning requires experimenting with a wide range of datasets, data preparation steps, and algorithms to build a model that maximizes a target metric. Once you have built a model, you also need to deploy it to a production system, monitor its performance, and continuously retrain it on new data and compare it with alternative models.

## [Cloudera AI Experiment Tracking through MLflow API](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-tracking.html)

Cloudera AI’s experiment tracking features allow you to use the MLflow client library for logging parameters, code versions, metrics, and output files when running your machine learning code. The MLflow library is available in Cloudera AI Sessions without you having to install it. Cloudera AI also provides a UI for later visualizing the results. MLflow tracking lets you log and query experiments using the following logging functions:

## [Running an Experiment using MLflow](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-run-exp-mlflow.html)

This topic walks you through a simple example to help you get started with Experiments in Cloudera AI.

## [Visualizing Experiment Results](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-visualize-results.html)

After you create multiple runs, you can compare your results.

## [Deploying an MLflow model as a Cloudera AI Workbench Model (Legacy)](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-rest-api-model.html)

In the future, you will be able to register models to a Cloudera AI Registry and then deploy Model REST APIs with those models. Today, these models can be deployed using the following manual process instead

### [Using an MLflow Model Artifact in a Model REST API](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-mlflow-model-artifact.html)

You can use MLflow to create, deploy, and manage models as REST APIs to serve predictions

### [Downloading MLFlow models using API endpoint](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-downloading-mlflow-models-using-api-endpoint.html)

The API endpoint allows you to download a model artifact for a specific model version in the Cloudera AI Registry.

### [Registering and deploying models with Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-registering-and-deploying-a-model-registry.html)

After you have set up Cloudera AI Registry, you can create, register, and deploy models with AI Registry.

- [Creating a model using MLflow](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-creating-model-file.html): You can use MLflow to create a model.
- [Registering a model using the AI Registry user interface](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-registering-model-using-ui.html): You can register a model using the AI Registry user interface or the MLFlow SDK.
- [Registering a model using MLflow SDK](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-registering-model-using-mlflow-sdk.html): You can register a model using the user interface or the MLFlow SDK.
  - [Using MLflow SDK to register customized models](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-deploy-custom-mlflow.html): In MLflow, you can also deploy models that are not directly supported by MLFlow.
- [Creating a new version of a registered model](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-creating-new-model-version.html): Follow the instructions to create a new version of a registered model.
- [Deploying a model from the AI Registry page](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-deploying-model-from-model-registry-page.html): You can deploy a model once or more times to create different versions of the model. You can also deploy a model you created in one workbench to a different workbench.
  - [Deploying a model from the Cloudera AI Registry using APIv2](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-mr-deploy-model-api.html): You can use the API v2 to deploy registered models from the AI Registry as part of your MLOps CI/CD pipeline.
- [Deploying a model from the destination Project page](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-deploying-model-from-destination-project-page.html): You can deploy a model once or more times to create different versions of the model. You can also deploy a model you created in one workbench to a different workbench.
- [Viewing and synchronizing the Cloudera AI Registry instance](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-model-registry-viewing-details.html): You can view detailed information for Cloudera AI Registry.
- [Deleting a model from Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-delete-registered-model.html): You can delete a model from Cloudera AI Registry through the UI or using an API call.
- [Disabling Cloudera AI Registry](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-disabling-model-registry.html): By default, Cloudera AI Registry is enabled in Cloudera AI. You can disable Cloudera AI Registry if you do not want to use this feature.

## [Automatic Logging](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-auto-logging.html)

Automatic logging allows you to log metrics, parameters, and models without the need for an explicit log statement.

## [Setting Permissions for an Experiment](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-experiment-permissions.html)

Experiments are associated with the project ID, so permissions are inherited from the project. If you want to allow a colleague to view the experiments of a project, you should give them Viewer (or higher) access to the project.

## [MLflow transformers](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-mlflow-transformers.html)

This is an example of how MLflow transformers can be supported in Cloudera AI.

## [Evaluating LLM with MLflow](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-mlflow-evaluate-llm.html)

Cloudera AI’s experiment tracking features allow you to use MLflow APIs for LLMs evaluation. MLflow provides an API mlflow.evaluate() to help evaluate your LLMs. LLMs can generate text in various fields, such as answering questions, translation, and text summarization.

### [Using Heuristic-based metrics](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-mlflow-using-heuristic-based-metric.html)

The Heuristic-based metrics evaluate text or data using various heuristic metrics, such as, Rouge, Flesch-Kincaid, and BLEU. Below is a simple example of how MLflow LLM evaluation works.

### [Using LLM-as-a-Judge metrics](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-mlflow-using-llm-as-a-judge.html)

LLM-as-a-Judge is a new type of metric that uses LLMs to score the quality of model outputs, providing a more human-like evaluation for complex language tasks while being more scalable and cost-effective than human evaluation.

## [Known issues and limitations](https://docs.cloudera.com/machine-learning/1.5.5/experiments/topics/ml-exp-v2-known-issues.html)

Cloudera AI has the following known issues and limitations with experiments and MLflow.

