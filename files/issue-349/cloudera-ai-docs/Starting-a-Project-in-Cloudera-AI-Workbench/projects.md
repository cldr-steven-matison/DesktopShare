# Projects in Cloudera AI

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/projects/

Product: machine-learning 1.5.5

## [Managing Projects](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-projects.html)

Projects form the heart of Cloudera AI. They hold all the code, configuration, and libraries needed to reproducibly run analyses. Each project is independent, ensuring users can work freely without interfering with one another or breaking existing workloads.

### [Creating a Project with ML Runtimes variants](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-creating-a-project-with-runtimes-c.html)

Projects create an independent working environment to hold your code, configuration, and libraries for your analysis. This topic describes how to create a project with ML Runtimes variants in Cloudera AI.

### [Creating a project from a password-protected Git repo](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-create-project-from-password-git-repo.html)

You can create projects in Cloudera AI by replicating the project files from a Git repo. The Git repo can be public, or it can be private, accessed by SSH or HTTPS authentication.

### [Configuring Project-level Runtimes](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-using-project-level-runtime-configuration.html)

If you specified project-level Runtimes, you can view your chosen Runtime configuration by clicking Project Settings Runtime/Engine . Your chosen Runtimes are listed under Available Runtimes.

### [Adding project collaborators](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-adding-collaborators.html)

Learn how you can add collaborators to a project.

### [Modifying Project settings](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-modifying-project-settings.html)

Project contributors and administrators can modify aspects of the project environment such as the ML Runtimes used to launch sessions, the environment variables, or can create SSH tunnels to access external resources.

### [Managing Project Files](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-managing-files.html)

Cloudera AI allows you to move, rename, copy, and delete files within the scope of the project where they live. You can also upload new files to a project, or download project files. For use cases beyond simple projects, Cloudera strongly recommends using Git for Collaboration to manage your projects using version control.

### [Deleting a Project](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-deleting-a-project.html)

This topic demonstrates how to delete a project.

## [Native Workbench Console and Editor](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-workbench.html)

The workbench console provides an interactive environment tailored for data science, supporting R, Python and Scala. It currently supports R, Python, and Scala engines. You can use these engines in isolation, as you would on your laptop, or connect to your CDH cluster.

### [Launching a Session](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-launch-a-session.html)

Sessions allow you to perform actions such as run R or Python code. They also provide access to an interactive command prompt and terminal. This topic demonstrates how to launch a new session.

### [Run Code](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-execute-code.html)

This topic shows you how to enter and run code in the interactive Workbench command prompt or the editor after you launch a session. The editor can be best used for codes you want to keep, while the command prompt is an optimal choice for quick interactive exploration.

### [Access the Terminal](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-access-the-terminal.html)

Cloudera AI provides full terminal access to running engines from the web console. This topic show you how to access the Terminal from a running Workbench session.

### [Stop a Session](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-stop-a-session.html)

This topic demonstrates how to stop a session to free up resources for other users when you are finished.

### [Workbench editor file types](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-workbench-filetypes.html)

The default workbench editor supports the following file types:

## [Environmental Variables](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-environmental-variables.html)

Environmental variables help you customize engine environments, both globally and for individual projects/jobs.

## [Third-party Editors](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors.html)

In addition to the built-in Cloudera AI editor, you can configure Cloudera AI to work with third-party, browser-based IDEs such as Jupyter and also certain local IDEs that run on your machine, such as PyCharm.

### [Modes of configuration](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-configuration-modes.html)

The configuration for an Integrated Development Environment (IDE) depends on which type of editor you want to use.

### [Configure a browser-based IDE as an Editor](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-browser.html)

When you use a browser-based Integrated Development Environment (IDE), changes that you make in the editor are propagated to the Cloudera AI project.

- [Testing a browser-based IDE in a Session](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-test-browser-ide.html): This process can be used to ensure that a browser-based Integrated Development Environment (IDE) works as expected before you install it to a project or to a customized engine image. This process is not meant for browser-based IDEs that require root permission to install, such as RStudio.
- [Configuring a browser-based IDE at the Project level](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-browser-project.html): The following steps are only required if you want to use an editor that is not included in the default engine image that ships with Cloudera AI.

### [Configuring a local IDE using an SSH gateway](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-local-ide-configure.html)

The specifics on how to configure a local IDE to work with Cloudera AI are dependent on the local IDE you want to use.

### [Configure PyCharm as a local IDE](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-local-ide-pycharm.html)

Cloudera AI supports using editors on your machine that allow remote execution and/or file sync over SSH, such as PyCharm.

- [Add Cloudera AI as an Interpreter for PyCharm](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-workbench-interpretor-pycharm.html): In PyCharm, you can configure an SSH interpreter. Cloudera AI uses this method to connect to PyCharm and act as its interpreter.
- [Configure PyCharm to use Cloudera AI as the remote console](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-remote-console-workbench-pycharm.html)
- [(Optional) Configure the Sync between Cloudera AI and PyCharm](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-sync-workbench-pycharm.html): Configuring what files PyCharm ignores can help you adhere to IT policies.

### [Configure VS Code as a local IDE](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-editors-vs-code.html)

Follow the guidelines for configuring VS Code as a local Integrated Development Environment (IDE).

- [Download cdswctl and add an SSH Key](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-vs-code-download-cdswctl-and-add-ssh-key.html): The first step to configure VS Code as a local IDE is to download cdswctl and add an SSH key.
- [Initialize an SSH connection to Cloudera AI for VS code](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-initialize-ssh-connection-vs-code.html): The following task describes how to establish an SSH endpoint for Cloudera AI. Creating an SSH endpoint is the first step to configuring a remote editor for Cloudera AI.
- [Setting up VS Code](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-setting-up-vs-code.html): In VS Code, you can configure an SSH interpreter. Cloudera AI uses this method to connect to VS Code and act as its interpreter.
- [(Optional) Using VS Code with Python](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-vs-code-with-python.html): You can use VS Code with Python.
- [(Optional) Using VS Code with R](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-vs-code-with-R.html): You can use VS Code with R.
- [(Optional) Using VS Code with Jupyter](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-vs-code-with-jupyter.html): You can use VS Code with Jupyter Notebooks.
- [(Optional) Using VS Code with Git integration](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-vs-code-with-git-integration.html): VS Code has substantial Git integration.
- [Limiting files in Explorer view](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-vs-code-limiting-explorer-view-files.html): You can limit the number of files shown in the Explorer view.

## [Git for Collaboration](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-using-git.html)

Cloudera AI provides seamless access to Git projects. Whether you are working independently, or as part of a team, you can leverage all of benefits of version control and collaboration with Git from within Cloudera AI.

### [Linking an existing Project to a Git remote](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-linking-an-existing-project-to-a-git-remote.html)

If you did not create your project from a Git repository, you can link an existing project to a Git remote (for example, git@github.com:username/repo.git) so that you can push and pull your code.

## [Embedded Web Applications](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-embedded-web-apps.html)

This topic describes how Cloudera AI allows you to embed web applications for frameworks such as Spark 2, TensorFlow, Shiny, and so on within sessions and jobs.

### [Example: A Shiny Application](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-example--a-shiny-application.html)

This example demonstrates how to create and run a Shiny application and view the associated UI while in an active session.

### [Example: Flask application](https://docs.cloudera.com/machine-learning/1.5.5/projects/topics/ml-projects-embedded-web-applications-example-flask-application.html)

This example demonstrates how to create and use a Flask application.

