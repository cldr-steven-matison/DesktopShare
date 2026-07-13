---
layout: post
title: "Cloudera DataFlow CDC Iceberg Technical Preview"
date: "2026-05-13"
categories: [cblog]
tags: [nifi, dataflow, iceberg, readyflow, CDC, Debezium, Db2, MySQL, Oracle, PostgreSQL, SQL Server]
author: Steven Matison
excerpt: "Deep dive into Cloudera DataFlow’s brand-new CDC ReadyFlows. I walk through every supported source database (Db2, MySQL, Oracle, PostgreSQL, SQL Server) and both Iceberg and Kudu targets — complete with deployment setup, sample database details, and the exact steps you’ll need to get them running in your environment."
image: /assets/images/blog/cdf-cdc-preview-hero.png  <!-- placeholder for hero image -->
reading_time: "25 minute read"
---

# Hands-On Review of All Iceberg CDC ReadyFlows

Hey everyone, Steven Matison here — Cloudera Solutions Engineer and your guide through the modern Cloudera solutions around Apache NiFi.

Change Data Capture (CDC) is one of the most requested and most complicated capabilities in Cloudera Data Platform, and with the latest **Cloudera DataFlow (CDF) Cloud Technical Preview**, the team has delivered a full suite of **ReadyFlows** that make CDC with Iceberg developer-ready out of the box.

In this lesson, I’m going to introduce you to **every single CDC Iceberg ReadyFlow** currently available in the Cloudera documentation. For each one I’ll cover:

- Source and target systems  
- Exact setup and deployment details you’ll need to take
- Sample databases I’m using for testing (with DDL and seed data)  
- Configuration gotchas and best practices I find along the way 

Because this is a **Technical Preview**, things can (and probably will) evolve quickly — I’ll note what’s preview-only and where to watch for changes.

**This post is intentionally structured as a living framework.** I’ll be filling in the full step-by-step instructions, screenshots, configuration snippets, and test results in follow-up deep-dive sessions as I finish building and validating each flow in my lab environments. Think of this as the master blueprint and I will expand it as the Technical Preview goes to General Availability.

---

## Table of Contents
1. [Why CDC ReadyFlows Matter in Cloudera DataFlow](#why-cdc-readyflows-matter)  
2. [CDC ReadyFlow Overview](#cdc-readyflow-overview)  
3. [Db2 Iceberg CDC ReadyFlow](#db2-cdc-readyflow)  
4. [MySQL Iceberg CDC ReadyFlow](#mysql-cdc-readyflow)  
5. [Oracle Iceberg CDC ReadyFlow](#oracle-cdc-readyflow)  
6. [PostgreSQL Iceberg CDC ReadyFlow](#postgresql-cdc-readyflow)  
7. [SQL Server Iceberg CDC ReadyFlow](#sql-server-cdc-readyflow)  
8. [Common Deployment Patterns & Best Practices](#common-deployment-patterns)  
9. [Conclusion & What’s Next](#conclusion)  

---

## Why CDC ReadyFlows Matter in Cloudera DataFlow

Real-time replication from operational databases into modern data platforms is no longer a “nice-to-have.” Enterprises need it for:
- Near-real-time analytics on Iceberg tables
- Event-driven microservices
- Zero-ETL data pipelines

Cloudera’s new CDC ReadyFlows use battle-tested connectors (mostly Debezium under the hood) and wrap them in production-grade NiFi flows with built-in error handling, schema evolution support, and seamless integration into CDP’s security and governance model.

All of these Iceberg CDC flows are available today in the **ReadyFlow Catalog** inside Cloudera DataFlow Cloud.

---

## Iceberg CDC ReadyFlow Overview 

Cloudera currently ships **5 Iceberg CDC ReadyFlows**, grouped by source database:

| Source Database | Target: Iceberg (Technical Preview) |
|-----------------|-------------------------------------|
| **Db2**         | ✅ Db2 CDC to Iceberg              |
| **MySQL**       | ✅ MySQL CDC to Iceberg            |
| **Oracle**      | ✅ Oracle CDC to Iceberg           |
| **PostgreSQL**  | ✅ PostgreSQL CDC to Iceberg       |
| **SQL Server**  | ✅ SQL Server CDC to Iceberg       |

**Key notes on the preview**:
- All **Iceberg CDC** ReadyFlows are currently marked **Technical Preview**.
- ReadyFlows leverage Debezium for change data capture.
- Flows handle row-level INSERT/UPDATE/DELETE events and can be configured for schema evolution.

In the sections below I’ll break each one down with the exact setup details you’ll need to deploy them yourself.

---

## Db2 Iceberg CDC ReadyFlow

### Db2 CDC to Iceberg [Technical Preview]
**Description**: Captures CDC events from a Db2 source table and streams them into an Apache Iceberg destination table.

**Setup Details Needed to Deploy** (to be expanded in deep-dive session):
- [ ] Db2 CDC configuration on source (capture instance, etc.)
- [ ] Connection parameters for the Db2 CDC connector
- [ ] Iceberg catalog configuration in CDF
- [ ] Schema registry and record conversion settings

---

## MySQL Iceberg CDC ReadyFlow

### MySQL CDC to Iceberg [Technical Preview]
**Description**: Retrieves CDC events from a MySQL source table and streams them to an Iceberg destination table.

**Setup Details Needed to Deploy**:
- Binary logging must be enabled (`binlog_format=ROW`)
- User privileges for Debezium connector
- Iceberg target table creation

---

## Oracle Iceberg CDC ReadyFlow

### Oracle CDC to Iceberg [Technical Preview]
**Description**: Captures events from an Oracle table and streams them into Iceberg.

---

## PostgreSQL Iceberg CDC ReadyFlow

### PostgreSQL CDC to Iceberg [Technical Preview]
**Description**: Uses Debezium to retrieve events from a PostgreSQL table and stream them into Iceberg.

---

## SQL Server Iceberg CDC ReadyFlow

### SQL Server CDC to Iceberg [Technical Preview]
**Description**: Uses Debezium to retrieve events from a SQL Server table and stream them into Iceberg.

---

## Common Deployment Patterns & Best Practices

- Security & credentials management in CDF
- Schema evolution handling
- Error queues and dead-letter handling
- Scaling the flows
- Monitoring with Prometheus & Grafana
- Performance tuning tips I discover during testing

(I’ll expand this section heavily once all flows are running in the lab.)

---

## Conclusion & What’s Next

The new Iceberg CDC ReadyFlows in Cloudera DataFlow represent a massive leap forward for real-time data movement in the Cloudera on Cloud ecosystem. If you’re landing changes into Iceberg for lakehouse analytics and you need more CDC like capabilities these pre-built flows remove weeks of custom development.

**Stay tuned** — over the next few weeks I’ll be publishing the full deployment guides, sample databases, configuration files, and test results for each of these ReadyFlows right here on the blog. We’ll turn this framework into the most complete hands-on CDC reference available for Cloudera customers.

If you’re already on CDP Private Cloud or CDF Cloud and want to try these in your environment, drop me a note on X [@StevenMatison](https://x.com/StevenMatison) or LinkedIn — happy to compare notes or help you get the first flow running.