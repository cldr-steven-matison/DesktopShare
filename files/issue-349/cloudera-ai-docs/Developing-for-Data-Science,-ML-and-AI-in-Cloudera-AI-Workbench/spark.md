# Apache Spark 2 and Spark 3 on Cloudera AI

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/spark/

Product: machine-learning 1.5.5

## [Spark on Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-apache-spark-overview.html)

## [Apache Spark supported versions](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-spark-supported-versions.html)

Supported Apache Spark versions are available through Runtime add-ons that can be selected when starting a session.

## [Spark configuration files](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-spark-configuration-files.html)

Cloudera AI supports configuring Spark 2 and Spark 3 properties on a per project basis with the spark-defaults.conf file. If there is a file called spark-defaults.conf in your project root, this will be automatically be added to the global Spark defaults.

## [Managing memory available for Spark drivers](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-managing-memory-available-for-spark-drivers.html)

## [Managing dependencies for Spark 2 jobs](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-managing-dependencies-for-spark-2-jobs.html)

As with any Spark job, you can add external packages to the executor on startup. To add external dependencies to Spark jobs, specify the libraries you want added by using the appropriate configuration parameter in a spark-defaults.conf file.

## [Spark Log4j configuration](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-spark-logging-configuration.html)

Cloudera AI allows you to update Spark’s internal logging configuration on a per-project basis. Spark logging properties can be customized for every session and job with a default file path found at the root of your project. You can also specify a custom location with a custom environment variable.

## [Setting up an HTTP Proxy for Spark 2](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-proxy-setup.html)

Follow the guidelines on how to set up an HTTP proxy for Spark 2.

## [Spark web UIs](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-spark-webui.html)

This topic describes how to access Spark web UIs from the Cloudera AI UI.

## [Using Spark 3 from R](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-installing-sparklyr.html)

R users can access Spark 3 using sparklyr. Although Cloudera does not ship or support sparklyr, we do recommend using sparklyr as the R interface for Cloudera AI.

## [Using Spark 2 from Scala](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-spark-and-scala.html)

This topic describes how to set up a Scala project for CDS 2.x Powered by Apache Spark along with a few associated tasks. Cloudera AI provides an interface to the Spark 2 shell (v 2.0+) that works with Scala 2.11.

### [Managing dependencies for Spark 2 and Scala](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-adding--spark-scala-packages-jars.html)

This topic demonstrates how to manage dependencies on local and external files or packages.

## [Running Spark with Yarn on the Cloudera base cluster](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-spark-pushdown.html)

The primary supported way to run Spark workloads on Cloudera AI uses Spark on Kubernetes. This is different from Cloudera Data Science Workbench, which uses Spark on Yarn to run Spark workloads.

### [Enabling Spark Pushdown configuration for projects](https://docs.cloudera.com/machine-learning/1.5.5/spark/topics/ml-enabling-spark-pushdown-configuration-for-project-users.html)

Enable portforwarding rules and default spark configurations to allow spark job executors to be scheduled in Yarn in the base cluster.

