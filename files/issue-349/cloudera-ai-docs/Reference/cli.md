# Command Line Tools in Cloudera AI

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/cli/

Product: machine-learning 1.5.5

## [Command Line Tools in Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli.html)

Cloudera AI ships with the following command line tools. The purpose of each tool differs.

## [cdswctl Command Line Interface client](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-client.html)

Cloudera AI ships with a Command Line Interface (CLI) client that you can download from the Cloudera AI web UI.

### [Downloading and configuring cdswctl](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-client-config.html)

This topic describes how to download the cdswctl CLI client and configure your SSH public key to authenticate CLI access to sessions.

### [Initializing an SSH endpoint](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-create-ssh-endpoint.html)

This topic describes how to establish an SSH endpoint for Cloudera AI.

### [Logging into cdswctl](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-log-into-cdswctl.html)

This topic describes how to log into cdswctl.

### [Preparing to manage models for using the model CLI](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-preparing-to-manage-models-using-cli.html)

Before you can start using the model CLI to automate model deployment or to perform any other tasks, you must install the scikit-learn machine learning library for Python through the Cloudera AI web UI.

### [Creating a model using the model CLI](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-creating-model.html)

Follow the instructions on how to create models using the model CLI.

### [Build and deployment commands for models](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-listing-model-builds-and-deployments.html)

Models have separate parameters for builds and deployments. When a model is built, an image is created. Whereas, the deployment is the actual instance of the model. You can list model builds and deployment, and monitor their state using from model CLI client (cdswctl).

### [Deploying a new model with updated resources](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-redeploy-model-with-updated-resources.html)

You can republish a previously-deployed model in a new serving environment with an updated number of replicas or memory/CPU/GPU allocation by providing the model build ID of the model you want to rebuild.

### [Viewing replica logs for a model](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-viewing-replica-logs.html)

When a model is deployed, Cloudera AI enables you to specify the number of replicas that must be deployed to serve requests. If a replica crashes or fails to come up, you can diagnose it by viewing the logs for every replica using the model CLI.

### [Using ML Runtimes with cdswctl](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-using-runtimes-with-cdswctl.html)

If a project is configured to use ML Runtimes, cdswctl workflows for starting sessions or models are slightly different.

- [Querying the engine type](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-query-engine-type.html): You can query whether a project is configured using ML Runtimes or Legacy Engine.
- [Listing ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-listing-runtimes.html): The first step to working with projects using ML Runtimes is to query the available ML Runtimes using the cdswctl runtimes list command.
- [Starting sessions and creating SSH endpoints](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-starting-sessions-and-creating-ssh-endpoints.html): Once you choose a Runtime, you can start a session using the cdswctl sessions start command and create SSH endpoints using the cdswctl ssh-endpoint command.
- [Creating a model](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-cli-creating-model-runtimes.html): Creating a model in a project that uses ML Runtimes is similar to model creation with a legacy engine, but you must use a different parameter to specify the Runtime ID.

## [cdswctl command reference](https://docs.cloudera.com/machine-learning/1.5.5/cli/topics/ml-model-cli-command-reference.html)

You can manage your Cloudera AI Workbench cluster with the CLI client (cdswctl) that exists within the Cloudera AI Workbench. Running cdswctl without any arguments prints a brief description of each command.

