# Distributed Computing with Workers

> Canonical URL: https://docs.cloudera.com/machine-learning/1.5.5/distributed-computing/

Product: machine-learning 1.5.5

## [Distributed Computing with Workers](https://docs.cloudera.com/machine-learning/1.5.5/distributed-computing/topics/ml-parallel-computing.html)

Cloudera AI provides basic support for launching multiple engine instances, known as workers, from a single interactive session. Any R or Python session can be used to spawn workers. These workers can be configured to run a script (for example, a Python file) or a command when they start up.

### [Using workers API](https://docs.cloudera.com/machine-learning/1.5.5/distributed-computing/topics/ml-workers-api.html)

Using workers API enables parallelized task execution by launching multiple workers from a session, allowing them to process queued parameters with a specified function, making it ideal for use cases like web scraping or other distributed computations.

### [Worker Network Communication](https://docs.cloudera.com/machine-learning/1.5.5/distributed-computing/topics/ml-worker-network-communication.html)

This section demonstrates some trivial examples of how two worker engines communicate with the master engine.

