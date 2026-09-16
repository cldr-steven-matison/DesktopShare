# Using PBJ Workbench

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/runtimes/

Product: machine-learning 1.5.5

## [Using PBJ Workbench](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-pbj-workbench-requirements.html)

PBJ Workbench offers a classic workbench user interface powered by the open-source Jupyter protocol prepackaged within a runtime image. Users can select this runtime image when launching a session. The open-source Jupyter infrastructure eliminates the dependency on proprietary Cloudera AI code for building a Docker images, enabling faster creation of runtime images. PBJ Workbench enables you to build runtime images using Ubuntu base images or Chainguard images, including non-Cloudera base images, and integrate them with the Cloudera AI Workbench.

### [Requirements for using a PBJ Workbench](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-requirements-using-pbj-workbench.html)

Learn about the prerequisites and preparation steps for setting up a PBJ Workbench.

### [Dockerfile compatible with PBJ Workbench](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-pbj-workbench-dockerfile.html)

This Dockerfile produces a runtime image that is compatible with the PBJ Workbench from a third-party base image.

### [PBJ Runtimes and Models](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-models-in-pbj-workbench.html)

The PBJ (Powered by Jupyter) Runtime enables a wide variety of language kernels to be run as Cloudera AI workloads. Model workloads are currently only supported for Python and R kernels.

### [Example models with PBJ Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-pbj-models.html)

The library cml includes the package, models_v1. This package includes the cml_model decorator that can be used to allow a function to work as a model in a PBJ Runtime. It can also be used to enable gathering of model metrics.

## [Using ML Runtimes add-ons](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-using-runtimes-addons.html)

ML Runtimes add-ons allow you to add Spark and Hadoop CLI to sessions run on projects using ML Runtimes images.

### [Adding Hadoop CLI to ML Runtime sessions](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-adding-hadoop-cli-to-runtime-sessions.html)

Hadoop CLI can be enabled only on sessions that are selected to use Spark.

### [Adding Spark to ML Runtime Sessions](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-adding-spark-to-runtimes-sessions.html)

You can add Spark to ML Runtime sessions using the ML Runtimes add-ons. Both Spark and Hadoop CLI are enabled when you enable Spark.

### [Turning off ML Runtimes add-ons](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-turning-off-runtimes-addons.html)

ML Runtimes add-ons is turned on by default. However, you can disable ML Runtimes add-ons.

## [ML Runtimes NVIDIA GPU Edition](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-runtimes-nvidia-gpu.html)

The NVIDIA GPU Edition Runtimes are built on top of NVIDIA CUDA docker images. CUDA is a parallel computing platform and programming model developed by NVIDIA for general computing on graphical processing units (GPUs). With CUDA, developers can dramatically speed up computing applications by harnessing the power of GPUs.

### [Testing ML Runtime GPU Setup](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-test-runtime-with-gpu.html)

You can use the following simple examples to test whether the new ML Runtime is able to leverage GPUs as expected.

## [ML Runtimes NVIDIA RAPIDS Edition](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-runtimes-nvidia-rapids.html)

The RAPIDS Edition Runtimes are built on top of community built RAPIDS docker images. The RAPIDS suite of software libraries gives you the freedom to execute end-to-end data science and analytics pipelines entirely on GPUs. It relies on NVIDIA CUDA primitives for low-level compute optimization, but exposes that GPU parallelism and high-bandwidth memory speed through user-friendly Python interfaces.

## [Using Editors for ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-runtimes-using-editors.html)

Cloudera AI provides a Workbench UI to edit and run code, but we also provide a preconfigured JupyterLab runtime to allow this. Choose the editor you prefer when launching a ML Runtime session.

### [Using JupyterLab with ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-runtimes-jupyter.html)

JupyterLab is a web-based interactive development environment for Jupyter notebooks, code, and data.

- [Installing a Jupyter extension](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-installing-jupyter-extension.html): Extensions modify the appearance or behaviour of Jupyter applications (including JupyterLab and Jupyter Notebook).
- [Installing a Jupyter kernel](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-installing-jupyter-kernel.html): Jupyter kernels function like connections through which a notebook (or other part of JupyterLab) can talk to a particular interpreter. CDSW includes one kernel in each JupyterLab Runtime: Python 3.6, Python 3.7, or Python 3.8.
- [Installing R Kernel in JupyterLab Runtimes of Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-installing-r-kernel-jupiterlab-runtimes.html): To add R Kernel to JupyterLab Runtimes, create a Dockerfile that specifies the packages to be installed, in addition to the base image.
- [Using Conda Runtime](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-using-conda-runtime.html): Users now can create their own Python or R Conda environments within their Cloudera AI Projects that they can use in the JupyterLab editor.

## [Installing additional ML Runtimes Packages](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-install-pkg-lib-runtimes.html)

ML Runtimes are preloaded with a few common packages and libraries for Python. However, a key feature of Cloudera AI is the ability of different projects to install and use libraries pinned to specific versions, just as you would on your local computer.

## [Restrictions for upgrading R and Python packages](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-upgrade-R-and-python-packages.html)

Some R and Python packages shall not be upgraded because doing so will break the Workbench UI.

## [Custom Runtime add-ons with Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-custom-runtime-addons.html)

Custom ML Runtimes enable you to create runtimes with your own choice of libraries and applications, but also to further customize existing ML Runtimes with additional configuration files or binaries such as connection drivers, without the effort of creating a new custom ML Runtime.

## [ML Runtimes environment variables](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-runtimes-environment-variables.html)

This topic describes how ML Runtimes environmental variables work. It also lists the different scopes at which they can be set and the order of precedence that will be followed in case of conflicts.

### [ML Runtimes Environment Variables List](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-engine-environment-variables-runtimes.html)

The following table lists Cloudera AI environment variables that you can use to customize your project environments. These can be set either as a site administrator or within the scope of a project or a job.

### [Accessing Environmental Variables from projects](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-accessing-runtimes-environmental-variables-from-projects.html)

Follow the guidelines to access environmental variables from your code.

## [Customized Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-customized-runtimes.html)

This topic explains how custom Runtimes work and when they shall be used.

### [Creating customized ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-creating-a-customized-runtimes-image.html)

This section walks you through the steps required to create your own custom ML Runtimes based on the ML Runtime images provided by Cloudera.

- [Creating a Dockerfile for the custom Runtime Image](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-create-a-dockerfile-for-the-new-custom-runtimes-image.html): Follow the instructions to create a Dockerfile for a custom image.
- [Metadata for custom ML Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-metadata-for-custom-runtimes.html): This topic addresses the metadata for custom ML Runtimes.
- [Customizing the editor](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-editor-customization.html): A third-party editor can be customized to work with ML Runtimes.
- [Building the new Docker Image](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-build-the-new-runtimes-image.html): Follow the instructions to use Docker to build a custom image.
- [Distributing the ML Runtime Image](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-distribute-the-runtime-image.html): Select a method to distribute a custom ML Runtime to all the hosts.
- [Adding a new customized ML Runtime through the Runtime Catalog](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-registering-customized-runtimes.html): Cloudera AI enables you to add customized ML Runtimes from the Runtime Catalog window.

### [Limitations to customized ML Runtime images](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-custom-runtime-limitations.html)

This topic lists some limitations associated with customized ML Runtime images.

## [ML Runtimes Pre-installed Packages overview](https://docs.cloudera.com/machine-learning/1.5.5/runtimes/topics/ml-list-of-ml-runtimes-pre-installed-packages.html)

Cloudera AI ships with several base engine images that include Python kernels, and frequently used libraries.

