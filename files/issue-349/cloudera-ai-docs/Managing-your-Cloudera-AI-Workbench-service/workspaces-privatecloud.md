# Provisioning a Cloudera AI Workbench

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/

Product: machine-learning 1.5.5

## [Provisioning a Cloudera AI Workbench](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-pvc-provision-ml-workspace.html)

In Cloudera AI on premises, the Cloudera AI Workbench provides a space for the data scientists' work. After your Administrator has created or given you access to an environment, you can set up a workbench.

### [Enabling Ring Fencing in Cloudera AI Workbench](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-provision-enabling-ring-fencing.html)

The Ring Fencing feature is available from Cloudera AI on premises 1.5.5 SP1 or higher releases. Ring fencing ensures that Cloudera AI infrastructure pods are exclusively scheduled on designated Cloudera AI nodes within the Kubernetes cluster.

## [Configuring Traefik timeout values for large file uploads and downloads](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-configure-traefik-readtimeout-large-file-uploads.html)

When uploading or downloading large files, the default timeout value for readTimeout, writeTimeout and idleTimeout errors in Traefik proxy might not be sufficient. You can set the Traefik proxy timeout to a new duration instead of the default value.

## [Monitoring Cloudera AI Workbenches](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-monitoring-workspaces.html)

This topic shows you how to monitor resource usage on your Cloudera AI Workbenches.

## [Removing Cloudera AI Workbenches](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-remove-workspaces.html)

This topic describes how to remove an existing Cloudera AI Workbench and clean up any cloud resources associated with the workbench. Currently, only Cloudera users with both the MLAdmin role and the EnvironmentAdmin account role can remove workbenches.

## [Upgrading Cloudera AI Workbenches](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-pvc-upgrade-workspaces.html)

Upgrade Cloudera AI Workbenches in Cloudera Embedded Container Service by using supported upgrade paths and recommended intermediate versions.

### [Managing Cloudera AI workloads during Control Plane database outage](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-cai-workloads-control-plane-database-down.html)

This topic outlines the impact of the Control Plane database outage on Cloudera AI workloads and provides guidance on managing deployments to minimize disruptions. While Cloudera AI workloads remain unaffected, the Control Plane and its associated services will experience downtime.

## [Backups for Cloudera AI Workbenches](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-backup-restore-workspace.html)

Cloudera AI enables the efficient creation of machine learning projects, jobs, experiments, machine learning models, and applications within workbenches. The data and metadata of these artifacts are stored in different types of storage systems in on premises environments or in external NFS-backed workbenches outside of an on premises environment.

### [Workbench backup and restore prerequisites](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-backup-restore-prereqs-pvc.html)

To backup and restore workbenches, check that the following prerequisites are satisfied.

### [Backing up a Cloudera AI Workbench](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-backup-workspace.html)

Backing up an Cloudera AI Workbench preserves all files, models, applications, and other assets in the workbench, although files in external NFS-backed workbenches are not backed up by Cloudera AI automatically.

### [Cleaning up and backing up the Cloudera AI Workbench database manually](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-manual-backup-cleanup-cloudera-ai-workbench-database.html)

With the help of the script you can manually back up and clean up the Cloudera AI Workbench database.

### [Restoring a Cloudera AI Workbench](https://docs.cloudera.com/machine-learning/1.5.5/workspaces-privatecloud/topics/ml-restore-workspace.html)

Restoring a backup overwrites the existing Cloudera AI Workbench (from which the backup was taken from) and automatically imports the restored data. All of the projects, jobs, applications and so on in the original workbench are recreated in the new one.

