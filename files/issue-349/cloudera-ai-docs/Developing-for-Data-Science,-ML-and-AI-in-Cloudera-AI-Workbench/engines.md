# Managing Engines

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/engines/

Product: machine-learning 1.5.5

## [Managing Engines](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-managing-engines.html)

This topic describes how to manage engines and configure engine environments to meet your project requirements.

### [Creating Resource profiles](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-managing-resource-profiles.html)

Resource profiles define how many vCPUs and how much memory the product will reserve for a particular workload (for example, session, job, model).

### [Configuring the engine environment](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-configuring-the-engine-environment.html)

This section describes some of the ways you can configure engine environments to meet the requirements of your projects.

### [Set up a custom repository location](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-pip-cran-custom-repo.html)

You can set up a custom default location for Python and R code package repositories. This is especially useful for air-gapped clusters that are isolated from the PIP and CRAN repositories on the public internet.

### [Burstable CPUs](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-burstable-cpu.html)

Cloudera AI configures no upper bound on the CPU resources that Workloads can use so that they can use all of the CPU resources available on the node where they are running. By configuring no CPU limits, Cloudera AI enables efficient use of the CPU resources available on your cluster nodes.

## [Installing additional packages](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-install-pkg-lib.html)

Cloudera AI engines are preloaded with a few common packages and libraries for R, Python, and Scala. However, a key feature of Cloudera AI is the ability of different projects to install and use libraries pinned to specific versions, just as you would on your local computer.

### [Using Conda to manage dependencies](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-using-conda.html)

You can install additional libraries and packages from the workbench, using either the command prompt or the terminal. Alternatively, you might choose to use a package manager such as Conda to install and maintain packages and their dependencies. This topic describes some basic usage guidelines for Conda.

## [Engine environment variables](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-environment-variables.html)

This topic describes how engine environmental variables work. It also lists the different scopes at which they can be set and the order of precedence that will be followed in case of conflicts.

### [Engine environment variables](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-engine-environment-variables.html)

The following table lists Cloudera AI environment variables that you can use to customize your project environments. These can be set either as a site administrator or within the scope of a project or a job.

### [Accessing environmental variables from projects](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-accessing-environmental-variables-from-projects.html)

This topic shows you how to access environmental variables from your code.

## [Customized engine images](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-customized-engines.html)

This topic explains how custom engines work and when they shall be used.

### [Creating a customized engine image](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-creating-a-customized-engine-image.html)

This section walks you through the steps required to create your own custom engine based on the Cloudera AI base image.

- [Create a Dockerfile for the custom image](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-create-a-dockerfile-for-the-new-custom-image.html): This topic shows you how to create a Dockerfile for a custom image.
- [Build the new Docker image](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-build-the-new-image.html): This topic shows you how to use Docker to build a custom image.
- [Distribute the image](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-distribute-the-image.html): This topic explains the different methods that can be used to distribute a custom engine to all the hosts.
- [Including images in allowlist for Cloudera AI projects](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-whitelist-the-image-in-cloudera-data-science-workbench.html): This topic describes how to include custom images in the allowlist so that they can be used in projects.

### [Limitations with customized engines](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-custom-engine-limitations.html)

This topic lists some limitations associated with custom engines.

### [End-to-end example: MeCab](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-end-to-end-example--mecab.html)

This topic walks you through a simple end-to-end example on how to build and use custom engines.

## [Legacy Engine level configuration](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-editors-browser-engine.html)

You can make a browser-based Integrated Development Environment (IDE) available to any project within a Cloudera AI deployment by creating a customized legacy engine image, installing the editor to it, and adding it to the trusted list for a project. Additionally, browser IDEs that require root permission to install, such as RStudio, can only be used as part of a customized legacy engine image.

## [Pre-Installed Packages in engines](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-engines-packaging.html)

Cloudera AI ships with several base engine images that include Python and R kernels, and frequently used libraries.

### [Base Engine 15-cml-2021.09-1](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-15.html)

Engine 15 ships Python versions 2.7.18 and 3.6.13, and R version 3.6.3.

### [Base Engine 14-cml-2021.05-1](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-14.html)

Engine 14 ships Python versions 2.7.18 and 3.6.10, and R version 3.6.3.

### [Base Engine 13-cml-2020.08-1](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-13.html)

Engine 13 ships Python versions 2.7.18 and 3.6.10, and R version 3.6.3.

### [Base Engine 12-cml-2020.06-2](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-12.html)

Engine 12 ships Python versions 2.7.18 and 3.6.10, and R version 3.6.3.

### [Base Engine 11-cml1.4](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-11.html)

Engine 11 ships Python versions 2.7.17 and 3.6.9, and R version 3.6.2.

### [Base Engine 10-cml1.3](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-10.html)

Engine 10 ships Python versions 2.7.17 and 3.6.9, and R version 3.5.1.

### [Base Engine 9-cml1.2](https://docs.cloudera.com/machine-learning/1.5.5/engines/topics/ml-base-engine-9.html)

Engine 9 ships Python 2.7.11 and 3.6.8, and R version 3.5.1.

