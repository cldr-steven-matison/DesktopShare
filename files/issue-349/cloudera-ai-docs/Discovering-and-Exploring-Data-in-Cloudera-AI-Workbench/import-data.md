# Uploading and working with local files

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/import-data/

Product: machine-learning 1.5.5

## [Uploading and working with local files](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-accessing-local-data-from-your-computer.html)

To work with data files (.csv, .txt, and so on) existing on your computer, upload the files directly to your project in the Cloudera AI Workbench. The presented code samples demonstrate how to access local data for Cloudera AI workloads.

## [Auto discovering data sources](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-auto-discovering-data-sources.html)

Data connections listed in this section are automatically discovered and configured.

## [Using data connection snippets](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-mlde-using-snippet.html)

As a data scientist, you can connect your project to data with a data connection snippet.

## [Manual data connections to connect to data sources](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-manual-data-connections-to-connect-to-data-sources.html)

You can also set up data connections manually, which work across Cloudera environments. Follow the procedures to set up data connections.

### [Hive and Impala connections](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-hive-impala-connections.html)

Use the following guidelines to understand which JDBC URL parameters are supported when configuring Hive and Impala data connections in Cloudera AI Workbench.

- [Connecting to Cloudera Data Warehouse](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-access-cdw-from-cml.html): The provided examples use Kerberos for authentication when connecting to Cloudera Data Warehouse Hive, and Impala, which requires that the Keytab is set and there are proper permissions to access Cloudera Data Warehouse.
- [Setting up a Hive or Impala data connection manually](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-mlde-manual-data-connection.html): Data connections to Hive or Impala virtual warehouses within the same environment as the Cloudera AI Workbench are automatically discovered and configured. You can also set up a data connection manually, which works across Cloudera environments. Follow this procedure to set up a Hive or Impala data connection.
- [Connecting to Hive and Impala services on Cloudera on premises Base](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-connecting-impale-hive-cml-pvc.html): The provided examples use Kerberos for authentication when connecting to Cloudera Data Warehouse Hive, and Impala, which requires that the Keytab is set and there are proper permissions to access Cloudera Data Warehouse.

### [Setting up a Spark data connection](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-mlde-spark-data-connection.html)

Spark data connections within the same environment as Cloudera AI are automatically discovered, but you can also set up a connection manually. Follow this procedure to set up a Spark data connection.

### [Accessing data with Spark](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-access-data-with-spark.html)

When you are using Cloudera Data Warehouse, you can use Java Database Connectivity (JDBC).

- [Using JDBC Connection with PySpark](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-jdbc-with-pyspark.html): PySpark can be used with Java Database Connectivity (JDBC), but it is not recommended. The recommended approach is to use Impyla for JDBC connections.
- [Connecting to Iceberg tables](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-pvc-iceberg-connection.html): Cloudera AI supports data connections to Iceberg data lakes.
- [Connecting to Hive tables via HWC](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-connecting-hivetbls-hwc-pvc.html): To access Hive from Spark, Hive Warehouse Connector (HWC) is needed. You can use the HWC to access Hive-managed tables from Spark.
- [Connecting to Ozone filesystem](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-accessing-ozone-from-spark.html): In Cloudera AI, you can connect Spark to the Ozone object store with a script.

### [Accessing Ozone storage](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-access-ozone.html)

In Cloudera AI you can connect Cloudera AI to the Ozone object store using a script or command line commands.

- [Creating an Ozone data connection](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-pvc-ozone-connection.html): Cloudera AI supports data connections to Ozone file systems.
- [Connecting to Ozone filesystem](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-accessing-ozone-from-spark.html): In Cloudera AI, you can connect Spark to the Ozone object store with a script.
- [Accessing local files in Ozone](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-access-ozone-hdfscli.html): You can access files in Ozone on a local file system using hdfsCLI. This method works with both legacy engines and runtime sessions.
- [Connecting to external Amazon S3 buckets](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-accessing-data-in-amazon-s3-buckets.html): Every language in Cloudera AI has libraries available for uploading to and downloading from Amazon S3.

### [Connect to External SQL Databases](https://docs.cloudera.com/machine-learning/1.5.5/import-data/topics/ml-accessing-external-sql-databases.html)

Every language in Cloudera AI has multiple client libraries available for SQL databases.

