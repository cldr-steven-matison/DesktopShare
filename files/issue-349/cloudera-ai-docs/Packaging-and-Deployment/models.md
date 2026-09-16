# Managing Models

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/models/

Product: machine-learning 1.5.5

## [Managing Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-managing-models.html)

Cloudera AI allows data scientists to build, deploy, and manage models as REST APIs to serve predictions.

### [Models overview](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-models.html)

Cloudera AI allows data scientists to build, deploy, and manage models as REST APIs to serve predictions.

- [Models - Concepts and Terminology](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-concepts-and-terminology.html)

### [Cloudera AI Project Lifecycle](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-training-deployment.html)

This section provides an overview of model training and deployment using Cloudera AI.

### [Challenges with Machine Learning in production](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-challenges-in-prod.html)

One of the hardest parts of Machine Learning (ML) is deploying and operating ML models in production applications. These challenges fall mainly into the following categories: model deployment and serving, model monitoring, and model governance.

- [Challenges with model deployment and serving](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-challenges-model-deployment-serving.html): After models are trained and ready to deploy in a production environment, lack of consistency with model deployment and serving workflows can present challenges in terms of scaling your model deployments to meet the increasing numbers of ML usecases across your business.
- [Challenges with model monitoring](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-challenges-model-monitoring.html): Machine Learning (ML) models predict the world around them which is constantly changing. The unique and complex nature of model behavior and model lifecycle present challenges after the models are deployed.
- [Challenges with model governance](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-challenges-model-governance.html): Businesses implement ML models across their entire organization, spanning a large spectrum of usecases. When you start deploying more than just a couple models in production, a lot of complex governance and management challenges arise.
  - [Model visibility](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-visibility.html): A basic requirement for model governance is enabling teams to understand how machine learning is being applied in their organizations. This requires a canonical catalog of models in use. In the absence of such a catalog, many organizations are unaware of how their models work, where they are deployed, what they are being used for, and so on. This leads to repeated work, model inconsistencies, recomputing features, and other inefficiencies.
  - [Model explainability, interpretability, and reproducibility](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-explainability-interpretability-reproducibility.html): Models are often seen as a black box: data goes in, something happens, and a prediction comes out. This lack of transparency is challenging on a number of levels and is often represented in loosely related terms explainability, interpretability, and reproducibility.
  - [Model governance using Apache Atlas](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-governance-using-atlas.html): To address governance challenges, Cloudera AI uses Apache Atlas to automatically collect and visualize lineage information for data used in Cloudera AI workflows — from training data to model deployments.

### [Creating and deploying a model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-creating-and-deploying-a-model.html)

Using Cloudera AI, you can create any function within a script and deploy it to a REST API. In a Cloudera AI project, this is typically a predict function that accepts an input and returns a prediction based on the model's parameters.

- [Hosting an LLM as a Cloudera AI Workbench model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-creating-a-cloudera-ai-model.html): Cloudera AI Workbench models give you the flexibility to host, expose, and monitor a variety of AI and machine learning models and functions.
- [Deploying the Cloudera AI Workbench model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-deploying-the-cloudera-ai-workbench-model.html): Deploy a Cloudera AI Workbench model following the instructions.

### [Usage guidelines for deploying models with Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-usage-guidelines.html)

Consider these guidelines when deploying models with Cloudera AI.

### [Known Issues and Limitations with Model Builds and Deployed Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-models-known-issues-and-limitations.html)

### [Request/Response Formats (JSON)](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-calling-a-model.html)

Every model function in Cloudera AI takes a single argument in the form of a JSON-encoded object, and returns another JSON-encoded object as output. This format ensures compatibility with any application accessing the model using the API, and gives you the flexibility to define how JSON data types map to your model's datatypes.

### [Testing calls to a Model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-testing-model-calls.html)

### [Securing Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-securing-models.html)

You can secure your Cloudera AI models using Access keys or API keys.

- [Access Keys for Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-access-key.html): Each model in Cloudera AI has a unique access key associated with it. This access key is a unique identifier for the model.
- [API Key for Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-api-key-for-models.html): You can prevent unauthorized access to your models by specifying an API key in the Authorization header of your model HTTP request. This topic covers how to create, test, and use an API key in Cloudera AI.
  - [Enabling authentication](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-enabling-authentication.html): Restricting access using API keys is an optional feature. By default, the Enable Authentication option is turned on. However, it is turned off by default for the existing models for backward compatibility. You can enable authentication for all your existing models.
  - [Generating an API key](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-generating-model-api-key.html): If you have enabled authentication, then you need an API key to call a model. If you are not a collaborator on a particular project, then you cannot access the models within that project using the API key that you generate. You need to be added as a collaborator by the admin or the owner of the project to use the API key to access a model.
  - [Managing API Keys](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-managing-model-api-keys.html): The administrator user can access the list of all the users who are accessing the workbench and can delete the API keys for a user.

### [Workflows for active Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-updating-active-models.html)

This topic walks you through some nuances between the different workflows available for re-deploying and re-building models.

### [Technical metrics for Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-tech-metrics.html)

You can observe the operation of your models by using charts provided for technical metrics. These charts can help you determine if your models are under- or over-resourced, or are experiencing some problem.

### [Debugging issues with Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-models-debug.html)

This topic describes some common issues to watch out for during different stages of the model build and deployment process.

### [Deleting a Model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-deleting-a-model.html)

### [Configuring model metrics payload limit](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-configure-model-request-payload-size.html)

Model metrics have a configuration that restricts model request payload to 100 KB. You can increase the payload size if required.

### [Example - Model training and deployment (Iris)](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-models-examples.html)

This topic uses Cloudera AI's built-in Python template project to walk you through an end-to-end example where we use experiments to develop and train a model, and then deploy it using Cloudera AI.

- [Training the Model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-train-the-model.html): This topic shows you how to run experiments and develop a model using the fit.py file.
- [Deploying the Model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-deploy-the-model.html): This topic shows you how to deploy the model using the predict.py script from the Python template project.

## [Model Governance](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-governance.html)

To capture and view centralized information about your ML projects, models, and builds in Apache Atlas (Data Catalog) for a specific environment, governance must be enabled.

### [Enabling model governance](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-enabling-model-governance.html)

You must enable governance to capture and view information about your ML projects, models, and builds centrally from Apache Atlas (Data Catalog) for a given environment. If you do not select this option while provisioning Cloudera AI Workbenches, then integration with Atlas will not work.

### [ML Governance Requirements](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-governance-reqs.html)

You must ensure that the following requirements are satisfied in order to enable ML Governance on Private Cloud.

### [Registering training data lineage using a linking file](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-registering-lineage-for-model.html)

The Cloudera AI projects, model builds, model deployments, and associated metadata are tracked in Apache Atlas, which is available in the environment's SDX cluster. You can also specify additional metadata to be tracked for a given model build. For example, you can specify metadata that links training data to a project through a special file called the linking file (lineage.yaml).

### [Viewing lineage for a model deployment in Atlas](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-view-lineage-for-model-deployment-in-atlas.html)

You can view the lineage information for a particular model deployment and trace it back to the specific data that was used to train the model through the Atlas' Management Console.

## [Model Metrics](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-model-metrics.html)

Metrics are essential for tracking model performance. By using custom code, you can track specific model predictions and analyze the metrics.

### [Enabling model metrics](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-enabling-model-metrics.html)

Metrics are used to track the performance of the models. When you enable model metrics while creating a workbench, the metrics are stored in a scalable metrics store. You can track individual model predictions and analyze metrics using custom code.

### [Tracking model metrics without deploying a model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-tracking-model-metrics-without-deploying-model.html)

Cloudera recommends that you develop and test model metrics in a workbench session before actually deploying the model. This workflow avoids the need to rebuild and redeploy a model to test every change.

### [Tracking metrics for deployed models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-tracking-model-metrics-using-python.html)

When you have finished developing your metrics tracking code and the code that consumes the metrics, simply deploy the predict function from predict_with_metrics.py as a model. No code changes are necessary.

## [Using Registered Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-use-registered-models.html)

Registered Models offers a single view for models stored in Cloudera AI Registries across Cloudera Environments and facilitate easy deployment to Cloudera AI Inference service.

### [Deploying a model from Registered Models](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-deploy-model-from-registered-models.html)

You can deploy a model from the Registered Models page into Cloudera AI Inference service.

### [Viewing details of a registered model](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-view-details-registered-models.html)

You can view details like version information about the models in your AI Registries in the Registered Models page. By default, the latest version information is displayed. Model card describes the model, governing terms, the family of models, resources used, and further information on how to use the model, and so on. It also provides information about various versions, optimizations made in the specific version, and the minimum resource configuration required to deploy those versions.

### [Editing model visibility](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-edit-visibility-registered-models.html)

You can modify the visibility of the model to private or public status. If the visibility is set to Public, the registered model is available for all the users irrespective of their role. If the visibility is set to Private, the model is available only to the owner and the administrators of that environment.

### [Deleting a registered model version](https://docs.cloudera.com/machine-learning/1.5.5/models/topics/ml-delete-registered-models.html)

If you no longer want to access a version of a registered model, you can delete it.

