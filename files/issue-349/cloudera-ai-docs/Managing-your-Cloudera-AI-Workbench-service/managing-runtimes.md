# Managing ML Runtimes

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/

Product: machine-learning 1.5.5

## [Managing ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-runtimes-overview.html)

Provides overview, installation, set up, configuration, and customization information for ML Runtimes.

### [Adding new ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-adding-new-ml-runtimes.html)

Cloudera AI provides two ways to add new Runtimes to the Runtime Catalog.

### [Adding Custom ML Runtimes through the Runtime Catalog](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-adding-custom-ml-runtime-through-runtime-catalog.html)

### [Adding ML Runtimes using Runtime Repo files](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-adding-custom-ml-runtime-through-runtime-repo.html)

### [Updating ML Runtime images on Cloudera AI installations](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-updating-runtimes-images.html)

In on premises ML Runtimes, the collection of docker images are bundled as part of the package. However, you can upgrade Runtime images to the latest version any time and even if you have an air-gapped installation, that is, there is no or only limited Internet access.

### [ML Runtimes versus Legacy Engine](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-runtimes-vs-engines.html)

While Runtimes and the Legacy Engine are both container images that contain the Linux OS, interpreter(s), and libraries, ML Runtimes keeps the images small and improves performance, maintenance, and security.

### [Using Runtime Catalog](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-using-runtime-catalog.html)

You can use the Runtime catalog to list all runtimes that are available for your deployment. A Recommended label is added to some runtime variants recommended for use by Cloudera, so the adminstrator users can easily identify the optimal selections. Administrator users can set runtime variants as default runtime variants using the checkbox.

### [Changing Docker credential setting for ML Runtime](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-change-docker-credential-ml-runtime.html)

You can choose a specific Docker credential for Cloudera AI to use while fetching ML Runtime from a secure repository.

### [Enabling, disabling, and deprecating Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-disable-runtime.html)

A key feature of the Runtime Catalog is the ability to enable, disable or deprecate one or more Runtimes at once.

## [Using ML Runtimes add-ons](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-using-runtimes-addons.html)

ML Runtimes add-ons allow you to add Spark and Hadoop CLI to sessions run on projects using ML Runtimes images.

### [Managing ML Runtimes add-ons](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-managing-ml-runtimes-add-ons.html)

An ML Runtime add-on is a modular component used to extend the capabilities of a Cloudera AI environment without increasing the base image size.

- [Disabling or deprecating Runtime add-ons](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-site-admin-runtime-addons-settings.html): Disable or deprecate a Spark Runtime add-on.
- [ML Runtime add-on repository files](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-runtime-add-on-repository-file.html): ML Runtime add-on repository files are JSON files that contain the details of ML Runtime add-ons needed by Cloudera AI to load them into the workbench.
- [Uploading ML Runtime add-on repository files using the APIv2 endpoint](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-uploading-runtime-add-on-repository-files-using-apiv2-endpoint.html): Cloudera AI provides an APIv2 endpoint that allows Administrators to upload and register ML Runtime add-on repository files by submitting the JSON file as a multipart upload.

### [Adding Hadoop CLI to ML Runtime sessions](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-adding-hadoop-cli-to-runtime-sessions.html)

Hadoop CLI can be enabled only on sessions that are selected to use Spark.

### [Adding Spark to ML Runtime Sessions](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-adding-spark-to-runtimes-sessions.html)

You can add Spark to ML Runtime sessions using the ML Runtimes add-ons. Both Spark and Hadoop CLI are enabled when you enable Spark.

### [Turning off ML Runtimes add-ons](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-turning-off-runtimes-addons.html)

ML Runtimes add-ons is turned on by default. However, you can disable ML Runtimes add-ons.

## [Customized Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-customized-runtimes.html)

This topic explains how custom Runtimes work and when they shall be used.

### [Creating customized ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-creating-a-customized-runtimes-image.html)

This section walks you through the steps required to create your own custom ML Runtimes based on the ML Runtime images provided by Cloudera.

- [Creating a Dockerfile for the custom Runtime Image](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-create-a-dockerfile-for-the-new-custom-runtimes-image.html): Follow the instructions to create a Dockerfile for a custom image.
- [Metadata for custom ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-metadata-for-custom-runtimes.html): This topic addresses the metadata for custom ML Runtimes.
- [Customizing the editor](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-editor-customization.html): A third-party editor can be customized to work with ML Runtimes.
- [Building the new Docker Image](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-build-the-new-runtimes-image.html): Follow the instructions to use Docker to build a custom image.
- [Distributing the ML Runtime Image](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-distribute-the-runtime-image.html): Select a method to distribute a custom ML Runtime to all the hosts.
- [Adding a new customized ML Runtime through the Runtime Catalog](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-registering-customized-runtimes.html): Cloudera AI enables you to add customized ML Runtimes from the Runtime Catalog window.

### [Limitations to customized ML Runtime images](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-custom-runtime-limitations.html)

This topic lists some limitations associated with customized ML Runtime images.

### [Adding Docker registry credentials](https://docs.cloudera.com/machine-learning/1.5.5/managing-runtimes/topics/ml-add-docker-registry-credentials-runtimes.html)

To enable Cloudera AI to fetch custom ML Runtimes from a secure repository, as an Administrator you need to add Docker registry credentials. If you want to use different credentials for different runtimes, you can add more docker credentials using the UI and API v2 and use that credentials to fetch custom ML Runtimes.

