# Quota Management overview

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/quota-management/

Product: machine-learning 1.5.5

## [Quota Management overview](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-mgt-overview.html)

Quota Management is generally available in Cloudera AI on premises 1.5.5 SP3 and higher releases for fresh workbench installations. Quota Management enables you to control how resources are allocated within your Cloudera AI Workbench on user and on team level.

## [Enabling Quota Management in Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-mgt-enable.html)

To enable Quota Management in Cloudera AI it needs to be configured. Follow the recommended configuration guidelines.

## [Configuring Workbench Quota during provisioning the Cloudera AI Workbench](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-mgt-provision-workspace.html)

Configuring the quota for a specified workbench requires additional configuration settings besides provisioning the workbench for Quota Management.

### [Using the latest Quota Management feature](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-upgrade-cloudera-ai-workbench.html)

To use the latest Quota Management feature, upgrade Cloudera AI Workbench to the latest version.

- [Updating the quota for the service pool after the upgrade](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-updating-quota-service-pool-post-upgrade.html): Learn about updating the quota for the service pool following the upgrade.

## [Quota for Cloudera AI workloads](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-mgt-quota-workloads.html)

Quota management is implemented for both user and team level. A Cloudera AI Workbench is allocated a set amount of resources based on configured parameters at provisioning time. Within a workbench, resources available for workloads can be further subdivided into quotas at user and/or team level.

## [Dynamic user pool assignment in Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-dynamic-user-pool-assignment-cloudera-ai.html)

Cloudera AI uses a dynamic pool assignment mechanism to manage user resource quotas in Cloudera AI 1.5.5 SP3 and higher releases. When quota management is enabled, the system automatically provisions and assigns resource pools to users.

## [Resource Usage Dashboard](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-resource-usage-dashboard.html)

The Resource Usage Dashboard is developed on top of Quota Management to depict the resource usage metrics.

## [Limitations for Quota management](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-mgt-limitations.html)

Follow the recommendations on the limitations of Cloudera AI Quota management.

## [Yunikorn Gang scheduling](https://docs.cloudera.com/machine-learning/1.5.5/quota-management/topics/ml-quota-yunikorn-gang-scheduling-pvc.html)

Yunikorn Gang Scheduling is the default scheduling mechanism in Cloudera AI. Yunikorn schedules the workload pods when Quota Management is enabled.

