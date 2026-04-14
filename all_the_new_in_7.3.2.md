# All the New in 7.3.2

**Steven Matison's Cloudera Blog**

Cloudera Runtime 7.3.2 delivers a comprehensive set of new capabilities, modernizations, and performance improvements across the entire platform. This release modernizes the stack with JDK 17 support for multiple components (bringing better performance, security, and long-term maintainability), adds IPv6 dual-stack support in several services for enhanced network scalability and future-proofing, and includes major rebases such as Hadoop to 3.4.x. It also rolls forward all service packs and cumulative hotfixes from 7.3.1.100 through 7.3.1.706.

Key highlights include a completely redesigned React-based UI for Apache Atlas with improved search, filtering, and navigation; automated entity auto-purging and asynchronous metadata import for better metadata hygiene and scalability; the new Cloudera Storage Optimizer in Ozone that intelligently converts cold data to erasure coding for 45-60% storage savings; numerous Hive UX enhancements and new commands; G1 Garbage Collector defaults on JDK 17 for HDFS, Ozone, and others; plus targeted improvements in Cruise Control, HBase, Impala, Ranger, Phoenix, and more. Operational, security, and configuration enhancements round out the release, making upgrades smoother and deployments more efficient.


**Cloudera Runtime 7.3.2 – Component Version Rebases**

Here is a clean Markdown table summarizing **all explicit product/component rebases and version upgrades** from the official 7.3.2 release notes (extracted directly from each "What's New" sub-page).

| Component                  | Previous Version | New Version   | Type          | Notes |
|----------------------------|------------------|---------------|---------------|-------|
| Apache Atlas               | 2.1.0           | 2.4.0        | Component Upgrade | Full upstream rebase + UI and stability fixes |
| Apache Hadoop (HDFS)       | 3.x series      | 3.4.1        | Major Rebase  | Includes all features/fixes from 3.2–3.4 |
| Apache Hadoop (Cloud Connectors) | 3.x series | 3.4.2        | Major Rebase  | Dedicated Cloud Connectors rebase |
| Apache HBase               | 2.4.17          | 2.6.3        | Component Upgrade | Upstream stability + performance fixes |
| Apache Kafka               | 3.4.1           | 3.9.1        | Major Rebase  | Full rebase through 3.5–3.9.1 |
| Apache Phoenix             | 5.1.3           | 5.2.1        | Component Upgrade | Performance + cluster-wide metadata upgrade blocks |
| Apache Ranger              | 2.4.0           | 2.6.0        | Component Upgrade | Latest fixes while maintaining compatibility |
| Apache Spark (Spark 3)     | —               | 3.5.4        | Major Rebase  | Rebase of Spark 3 to 3.5.4 |

**Components with no major upstream version rebase in 7.3.2** (only feature additions, JDK 17 support, IPv6, or hotfixes):
- Cruise Control
- Hive
- Cloudera Data Explorer (Hue)
- Iceberg
- Impala
- Knox
- Kudu (JDK 17 only)
- Livy
- Navigator Encrypt
- Oozie
- Ozone (no core version change)
- Ranger KMS
- Schema Registry
- Solr
- Spark Atlas Connector
- Sqoop
- Streams Messaging Manager
- Streams Replication Manager
- YARN / YARN Queue Manager
- Zookeeper

**Platform-wide changes** (not component-specific rebases):
- Widespread JDK 17 adoption (most services)
- IPv6 dual-stack support (multiple services)
- New OS support (RHEL 9.6, Rocky Linux 9.6, SLES 15 SP6, Ubuntu 24.04)
- New DB support (MariaDB 11.4)


## What's New in 7.3.2
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

## Summary

Cloudera Runtime 7.3.2 is a major modernization release for CDP Private Cloud Base. It delivers widespread JDK 17 adoption, IPv6 dual-stack networking, a Hadoop 3.4.x rebase, and dozens of new capabilities across every layer of the platform — from the redesigned React UI in Atlas and automated metadata purging, to the game-changing Cloudera Storage Optimizer in Ozone that can deliver 45-60% storage savings on cold data. With extensive Hive UX improvements, default G1GC on JDK 17 for multiple services, new platform OS and database support, and targeted enhancements in Ranger, Impala, Phoenix, Cruise Control, and beyond, this release provides immediate operational, performance, and security benefits while future-proofing your environment.

Whether you are upgrading for the new features, the stability improvements, or the long-term supportability gains, 7.3.2 represents a significant step forward for any Cloudera deployment.

---

## Resources

- [Cloudera What's New in Cloudera Runtime 7.3.2](https://docs.cloudera.com/cdp-private-cloud-base/7.3.2/private-release-notes/topics/rt-whats-new.html)  
- [Cloudera Runtime 7.3.2 Full Release Notes](https://docs.cloudera.com/cdp-private-cloud-base/7.3.2/private-release-notes/topics/rt-release-notes.html)  
- [Previous Release Post: Cloudera Runtime 7.3.2](/release/Introducing-Cloudera-Runtime-7.3.2/)


## {{ page.title }}
If you would like a deeper dive, hands on experience, demos, or are interested in speaking with me further about {{ page.title }} please reach out to schedule a discussion.


