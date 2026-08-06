## Trial Installation

This installer will download Cloudera Manager and guide you through the [setup process](https://docs.cloudera.com/cdp-private-cloud-base/7.1.7/installation/topics/cdpdc-trial-installation.html) to setup a Cloudera Base on premises cluster. This creates a self-contained environment and doesn’t require installing any additional software (Cloudera on premises can be added on later through a separate process).  Users setting up a Cloudera Base on private cloud cluster for production use should not use these instructions but instead follow the [installation instructions](https://docs.cloudera.com/cdp-private-cloud-base/7.1.7/installation/topics/cdp-quick-start-streams-run-cm-server-installer.html) in Cloudera documentation.

**Note:** *A trial installation cannot easily be upgraded, backed up, or migrated into a production-ready configuration without manual steps, described [here](https://docs.cloudera.com/cdp-private-cloud-base/7.1.7/installation/topics/cdpdc-install-reference.html). If you plan to migrate this system into a production system, consider using the Production Installation process described [here](https://docs.cloudera.com/cdp-private-cloud-base/latest/installation/topics/cdpdc-installation.html) instead.*

Pre-requisites: Creating a Cloudera Base on premises cluster requires multiple, Internet-connected [Linux](https://docs.cloudera.com/cdp/latest/release-guide/topics/cdpdc-os-requirements.html) machines. For details please see the [CDP system requirements](https://docs.cloudera.com/cdp-private-cloud-base/7.1.7/installation/topics/cdpdc-requirements-supported-versions.html).

Installation instructions:  Type the following at a Linux command prompt to begin an automated CDP installation.

```bash
$wget [https://archive.cloudera.com/cm7/7.4.4/cloudera-manager-installer.bin$](https://archive.cloudera.com/cm7/7.4.4/cloudera-manager-installer.bin$) chmod u+x cloudera-manager-installer.bin
$ sudo ./cloudera-manager-installer.bin

```