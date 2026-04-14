# All the New in 7.3.2

**Steven Matison's Cloudera Blog**

Cloudera Runtime 7.3.2 delivers a comprehensive set of new capabilities, modernizations, and performance improvements across the entire platform. This release modernizes the stack with JDK 17 support for multiple components (bringing better performance, security, and long-term maintainability), adds IPv6 dual-stack support in several services for enhanced network scalability and future-proofing, and includes major rebases such as Hadoop to 3.4.x. It also rolls forward all service packs and cumulative hotfixes from 7.3.1.100 through 7.3.1.706.

Key highlights include a completely redesigned React-based UI for Apache Atlas with improved search, filtering, and navigation; automated entity auto-purging and asynchronous metadata import for better metadata hygiene and scalability; the new Cloudera Storage Optimizer in Ozone that intelligently converts cold data to erasure coding for 45-60% storage savings; numerous Hive UX enhancements and new commands; G1 Garbage Collector defaults on JDK 17 for HDFS, Ozone, and others; plus targeted improvements in Cruise Control, HBase, Impala, Ranger, Phoenix, and more. Operational, security, and configuration enhancements round out the release, making upgrades smoother and deployments more efficient.

Below is the complete structure with every “What’s New” section from the official Cloudera Runtime 7.3.2 Release Notes. All deeper links and references to Cloudera documentation can be preserved when you paste the content yourself.

## Table of Contents
- [What’s New in Platform Support](#platform-support)
- [What’s New in Apache Atlas](#atlas)
- [What’s New in Cloud Connectors](#cloud-connectors)
- [What’s New in Cruise Control](#cruise-control)
- [What’s New in Apache HBase](#hbase)
- [What’s New in HDFS](#hdfs)
- [What’s New in Hive](#hive)
- [What’s New in Cloudera Data Explorer (Hue)](#hue)
- [What’s New in Iceberg](#iceberg)
- [What’s New in Impala](#impala)
- [What’s New in Kafka](#kafka)
- [What’s New in Knox](#knox)
- [What’s New in Kudu](#kudu)
- [What’s New in Livy](#livy)
- [What’s New in Navigator Encrypt](#navencrypt)
- [What’s New in Oozie](#oozie)
- [What’s New in Ozone](#ozone)
- [What’s New in Phoenix](#phoenix)
- [What’s New in Ranger](#ranger)
- [What’s New in Ranger KMS](#rangerkms)
- [What’s New in Schema Registry](#schema-registry)
- [What’s New in Solr](#solr)
- [What’s New in Spark](#spark)
- [What’s New in Spark Atlas Connector](#sac)
- [What’s New in Sqoop](#sqoop)
- [What’s New in Streams Messaging Manager](#smm)
- [What’s New in Streams Replication Manager](#srm)
- [What’s New in YARN and YARN Queue Manager](#yarn)
- [What’s New in Zookeeper](#zookeeper)

---

<a id="platform-support"></a>
### What’s New in Platform Support

---

<a id="atlas"></a>
### What’s New in Apache Atlas

---

<a id="cloud-connectors"></a>
### What’s New in Cloud Connectors

---

<a id="cruise-control"></a>
### What’s New in Cruise Control

---

<a id="hbase"></a>
### What’s New in Apache HBase

---

<a id="hdfs"></a>
### What’s New in HDFS

---

<a id="hive"></a>
### What’s New in Hive

---

<a id="hue"></a>
### What’s New in Cloudera Data Explorer (Hue)

---

<a id="iceberg"></a>
### What’s New in Iceberg

---

<a id="impala"></a>
### What’s New in Impala

---

<a id="kafka"></a>
### What’s New in Kafka

---

<a id="knox"></a>
### What’s New in Knox

---

<a id="kudu"></a>
### What’s New in Kudu

---

<a id="livy"></a>
### What’s New in Livy

---

<a id="navencrypt"></a>
### What’s New in Navigator Encrypt

---

<a id="oozie"></a>
### What’s New in Oozie

---

<a id="ozone"></a>
### What’s New in Ozone

---

<a id="phoenix"></a>
### What’s New in Phoenix

---

<a id="ranger"></a>
### What’s New in Ranger

---

<a id="rangerkms"></a>
### What’s New in Ranger KMS

---

<a id="schema-registry"></a>
### What’s New in Schema Registry

---

<a id="solr"></a>
### What’s New in Solr

---

<a id="spark"></a>
### What’s New in Spark

---

<a id="sac"></a>
### What’s New in Spark Atlas Connector

---

<a id="sqoop"></a>
### What’s New in Sqoop

---

<a id="smm"></a>
### What’s New in Streams Messaging Manager

---

<a id="srm"></a>
### What’s New in Streams Replication Manager

---

<a id="yarn"></a>
### What’s New in YARN and YARN Queue Manager

---

<a id="zookeeper"></a>
### What’s New in Zookeeper

---

