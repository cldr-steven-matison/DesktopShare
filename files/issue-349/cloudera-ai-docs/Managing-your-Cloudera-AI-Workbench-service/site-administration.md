# Managing Users

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/site-administration/

Product: machine-learning 1.5.5

## [Managing Users](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-managing-users-as-a-site-administrator.html)

This topic describes how to manage a Cloudera AI Workbench as a site administrator. Site administrators can monitor and manage all user activity across a workbench, add new custom engines, and configure certain security settings.

## [Service Accounts](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-service-accounts.html)

Service accounts are used by machine users that require a user account, without the need of using an account of an actual user.

### [Creating a machine user and synchronizing to workbench](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-service-accounts-create.html)

The MLAdmin role is required to create machine users.

### [Synchronizing machine users from the Synced team](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-service-accounts-sync-team.html)

You can synchronize machine users that are part of a synced team to your project.

### [Running workloads using a service account](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-service-accounts-run-workloads.html)

You can run various types of workloads using a service account. First, make sure the service account is available in your project.

### [Authenticating Hadoop for Cloudera AI service accounts](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-service-accounts-auth-hadoop.html)

In Cloudera AI, the Kerberos principal for the Service Account may not be the same as your login information. Therefore, ensure you provide the Kerberos identity when you sign in to the Service Account.

## [Configuring quotas](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-quotas.html)

This topic describes how to configure CPU, GPU, and memory quotas for users of an Cloudera AI Workbench.

## [Non-user dependent Resource Usage Limiting for workloads](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-adminitrstation-resource-limiting.html)

The Resource Usage Limiting feature enables the utilization of CPU and memory independent of the user, in a way that no resource is unnecessarily blocked.

### [Setting Resource Usage Limiting for workloads](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-setting-resource-limits-for-workloads.html)

To enable Resource Usage Limiting follow the instructions.

## [Creating Resource profiles](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-managing-resource-profiles.html)

Resource profiles define how many vCPUs and how much memory the product will reserve for a particular workload (for example, session, job, model).

## [Disabling or deprecating Runtime add-ons](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-admin-runtime-addons-settings.html)

Disable or deprecate a Spark Runtime add-on.

## [Onboarding Business Users](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-onboarding-biz-user.html)

There are two procedures required for adding Business Users to Cloudera AI. First, an Administrator ensures the Business User has the correct permissions, and second, a Project Owner adds the Business User as a Collaborator.

## [Adding a collaborator](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-adding-a-collaborator.html)

Project owners can add collaborators to a project.

## [User roles](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-user-roles.html)

Users in Cloudera AI are assigned one or more of the following roles.

### [Business Users and Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-biz-user-and-cml.html)

A user is considered a Business User in Cloudera AI if they are assigned the MLWorkspaceBusinessUser role on the workbench resource role assignment. Inside the workbench, a Business User is able to access and view applications, but does not have privileges to access any other workloads in the workbench.

### [Managing your Personal Account](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-managing-your-personal-account.html)

You can edit personal account settings such as email, SSH keys and Hadoop credentials.

### [Creating a Team](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-creating-a-team.html)

Users who work together on more than one project and want to facilitate collaboration can create a Team. Teams enable you to efficiently manage the users assigned to projects.

### [Managing a Team Account](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-modifying-team-account-settings.html)

Team administrators can modify account information, add or invite new team members, and view/edit privileges of existing members.

## [Monitoring user activity](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-monitoring.html)

This topic describes how to monitor user activity on an Cloudera AI Workbench.

### [Tracked user events](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-monitoring-tracked-events.html)

The tables on this page describe the user events that are logged by Cloudera AI.

### [Monitoring user events](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-monitoring-user-events.html)

This topic shows you how to query the PostgresSQL database that is embedded within the Cloudera AI deployment to monitor or audit user events.

### [Collecting project size information](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-administration-collecting-project-size.html)

Configure your project size information to be available in your Cloudera AI Workbench.

## [Monitoring active Models across the Workbench](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-admin-model-monitoring.html)

This topic describes how to monitor all active models currently deployed on your workbench.

## [Monitoring and alerts](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-monitoring-and-alerts.html)

Cloudera AI leverages Cloudera Monitoring based on Prometheus and Grafana to provide dashboards that allow you to monitor how CPU, memory, storage, and other resources are being consumed by your Cloudera AI Workbenches.

## [Application polling endpoint](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-custom-polling-endpoint.html)

The Cloudera AI server periodically polls applications for their status. The default polling endpoint is the root endpoint ( / ), but a custom polling endpoint can be specified if the server or other application has difficulty with the default endpoint.

## [Choosing default engine](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-default-engine.html)

This topic describes how to choose a default engine for creating projects.

## [Controlling User access to features](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-feature-control.html)

Cloudera AI provides Site Administrators with the ability to restrict or hide specific functionality that non-Site Administrator users have access to in the UI. For example, a site administrator can hide the models and experiments features from the Cloudera AI Workbench UI.

## [Setting custom Spark configurations at workbench-level](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-set-custom-spark-configurations.html)

Administrators can configure custom Spark settings at the Cloudera AI Workbench level. These configurations will then be applied to all projects and newly launched Spark sessions within that workbench. Non-administrator users can view the applied configurations from Cloudera AI 1.5.5 SP1, but cannot modify them at this level.

### [Enabling Spark pushdown configuration](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-enabling-spark-pushdown-configuration-for-projects.html)

Administrators must enable the Spark pushdown configuration option to grant users access to Spark pushdown within project configurations.

## [Enabling AI Studios](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-setting-up-enabling-ai-studios.html)

Administrators must enable the AI Studios option to allow users to build and deploy AI-powered applications.

## [Configuring Job Retry settings](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-administration-configuring-job-retry-administrator.html)

The Job Retry feature is available from Cloudera AI 1.5.5 SP1 or higher releases. Job retry runs are designed to operate asynchronously, ensuring they do not disrupt the normal flow of a job run. These retries are executed concurrently to maintain efficiency.

## [Disabling global Application restarts](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-administration-disable-global-application-restarts.html)

Disable automatic global application restarts in Cloudera AI by using Site Administration settings to manage workbench resource allocation and fault tolerance states.

## [Cloudera AI email notifications](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-email.html)

Cloudera AI allows you to send email notifications when you add collaborators to a project, share a project with a colleague, and for job status updates (email recipients are configured per-job). This topic shows you how to specify email address for such outbound communications.

## [Web session timeouts](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-web-session-timeouts.html)

You can set web sessions to time out and require the user to log in again. This time limit is not based on activity, it is the maximum time allowed for a web session.

## [Project garbage collection](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-garbage-collection.html)

Marks orpaned files for deletion from a project and cleans up projects that are marked for deletion.

## [How to make base cluster configuration changes](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-base-cluster-changes.html)

When you make base cluster configuration changes, you need to restart the base cluster to propagate those changes.

## [Ephemeral storage](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-ephemeral-storage.html)

Ephemeral storage space is scratch space that a Cloudera AI session, job, application or model can use. This feature helps in better scheduling of Cloudera AI pods, and provides a safety valve to ensure runaway computations do not consume all available scratch space on the node.

## [Non-transparent proxy setup on Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-setup-ntp-proxy.html)

Cloudera AI requires specific proxy configurations to manage workbench connections efficiently in an air-gapped setup with restricted outbound connections. This setup ensures seamless access to external resources while adhering to network security and management policies.

### [Updating proxy configuration in an existing workbench](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-updating-proxy-config-existing-workspace.html)

In order to enable new proxy configuration details update the new values under the Cloudera AI Workbench namespace and restart all deployments after the updates.

## [Export Usage List](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-export-usage-list.html)

You can export a list of sessions, jobs, workers, and experiments. You can either download a complete list of workloads or you can filter the workloads by date to download a more concise list. Timestamps in the list are given in Coordinated Universal Time (UTC).

## [Reviewing Runtime add-on compatibility](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-disable-addons.html)

As an on premises Administrator, you must ensure that Runtime add-ons used on your site are compatible with the base cluster version. This involves disabling any incompatible versions that may be installed.

## [Optimizing performance for scalability](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-optimizing-performance-for-scalability.html)

Optimize performance and scalability in Cloudera AI on premises by utilizing the Dashboards Archive feature, introduced in Cloudera AI on premises 1.5.5 CHF1, alongside configuring the livelog retention period and performing database cleanup, introduced in Cloudera AI on premises 1.5.5 SP1. The Dashboards Archive feature is designed to enhance system performance, manage data retention effectively, and provide a clear distinction between active and historical data within the dashboards system. Additionally, further performance optimization can be achieved by configuring the livelog retention period and cleaning up databases in Cloudera AI on premises.

### [Historical workload cleanup settings](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-historical-workload-cleanup-settings.html)

For optimizing performance you can configure livelog retention period and clean up databases from Cloudera AI on premises 1.5.5 SP1. Enable these features in Site Administration Settings under the Historical Workload Cleanup Settings option to enhance and optimize performance.

### [Optimized queries with Dashboards Archive table](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-site-adminisration-optimized-queries-dashboards-archive.html)

The Dashboards Archive feature introduces a mechanism from 1.5.5 CHF1 to optimize performance, manage data retention, and clarify the distinction between active and historical data in the dashboards system.

## [Host name required by Learning Hub](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-learning-hub-settings.html)

Learning Hub requires internet access to link to the displayed content. Learning Hub cannot be supported on a fully air-gapped cluster.

## [Configuring HTTP Headers for Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-http-headers.html)

This topic provides guidence on customizing the HTTP headers that are accepted by Cloudera AI.

### [Enable HTTP security headers](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-enable-http-security-headers.html)

### [Enable HTTP Strict Transport Security (HSTS)](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-enable-http-strict-transport-security--hsts-.html)

### [Enable Cross-Origin Resource Sharing (CORS)](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-enable-cross-origin-resource-sharing--cors-.html)

## [SSH Keys](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-ssh-keys.html)

### [Personal key](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-personal-key.html)

Cloudera AI automatically generates an SSH key pair for your user account. You can rotate the key pair and view your public key on your user settings page. It is not possible for anyone to view your private key.

### [Team key](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-team-key.html)

Team SSH keys provide a useful way to give an entire team access to external resources such as databases or GitHub repositories (as described in the next section).

### [Adding an SSH key to GitHub](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-adding-ssh-key-to-github.html)

Cloudera AI creates a public SSH key for each account. You can add this SSH public key to your GitHub account if you want to use password-protected GitHub repositories to create new projects or collaborate on projects.

### [Creating an SSH tunnel](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-ssh-tunnels.html)

You can use your SSH key to connect Cloudera AI to an external database or cluster by creating an SSH tunnel.

## [Hadoop authentication for Cloudera AI Workbenches](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-kerberos.html)

Cloudera AI does not assume that your Kerberos principal is always the same as your login information. Therefore, you will need to make sure Cloudera AI knows your Kerberos identity when you sign in.

## [Cloudera AI and outbound network access](https://docs.cloudera.com/machine-learning/1.5.5/site-administration/topics/ml-outbound-network-access.html)

Cloudera AI expects access to certain external networks. See the related information Configuring proxy hosts for Cloudera AI Workbench connections for further information.

