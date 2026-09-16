# Configuring HTTP Headers for Cloudera AI

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/security/

Product: machine-learning 1.5.5

## [Configuring HTTP Headers for Cloudera AI](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-http-headers.html)

This topic provides guidence on customizing the HTTP headers that are accepted by Cloudera AI.

### [Enable HTTP security headers](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-enable-http-security-headers.html)

### [Enable HTTP Strict Transport Security (HSTS)](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-enable-http-strict-transport-security--hsts-.html)

### [Enable Cross-Origin Resource Sharing (CORS)](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-enable-cross-origin-resource-sharing--cors-.html)

## [SSH Keys](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-ssh-keys.html)

### [Personal key](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-personal-key.html)

Cloudera AI automatically generates an SSH key pair for your user account. You can rotate the key pair and view your public key on your user settings page. It is not possible for anyone to view your private key.

### [Team key](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-team-key.html)

Team SSH keys provide a useful way to give an entire team access to external resources such as databases or GitHub repositories (as described in the next section).

### [Adding an SSH key to GitHub](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-adding-ssh-key-to-github.html)

Cloudera AI creates a public SSH key for each account. You can add this SSH public key to your GitHub account if you want to use password-protected GitHub repositories to create new projects or collaborate on projects.

### [Creating an SSH tunnel](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-ssh-tunnels.html)

You can use your SSH key to connect Cloudera AI to an external database or cluster by creating an SSH tunnel.

## [Hadoop authentication for Cloudera AI Workbenches](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-kerberos.html)

Cloudera AI does not assume that your Kerberos principal is always the same as your login information. Therefore, you will need to make sure Cloudera AI knows your Kerberos identity when you sign in.

## [Cloudera AI and outbound network access](https://docs.cloudera.com/machine-learning/1.5.5/security/topics/ml-outbound-network-access.html)

Cloudera AI expects access to certain external networks. See the related information Configuring proxy hosts for Cloudera AI Workbench connections for further information.

