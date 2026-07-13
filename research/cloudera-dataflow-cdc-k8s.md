### Recommended Setup Framework (CDC-Test Namespace)

Create a dedicated namespace so nothing touches your production Cloudera workloads:

```bash
kubectl create namespace cdc-test
```

We’ll use **StatefulSets + PVCs** (or full operators where they shine) for each DB. All support the exact CDC features the ReadyFlows need (LogMiner/supplemental logging for Oracle, logical replication for Postgres, binlog for MySQL, etc.).

### 1. Oracle (Highest Priority – Your ReadyFlow Focus)
**Best tool in 2026:** Oracle Database Operator for Kubernetes (OraOperator) v2.1.0  
- Fully Kubernetes-native, handles LogMiner, supplemental logging, PDBs, etc.
- Or for ultra-fast dev: official `container-registry.oracle.com/database/free` image in a simple StatefulSet (same as our old Docker plan, just wrapped in K8s).

**Quick install option (Operator – recommended):**
```bash
# Install via OperatorHub or Helm (community chart exists)
helm repo add oracle https://oracle.github.io/oracle-database-operator
helm install ora-operator oracle/oracle-database-operator --namespace cdc-test
```
Then apply a simple `OracleDatabase` CR with your CDC user and table (I’ll give you the exact YAML next).

**Fallback (fastest for testing):** StatefulSet + official image (I can write the full YAML in 2 minutes).

### 2. PostgreSQL (Easiest & Most Popular for Quick Wins)
**Best:** CloudNativePG (CNPG) or Percona Operator for PostgreSQL (both CNCF-grade and excellent for logical decoding / publications).

**Super-simple Helm route:**
```bash
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install pg-test cnpg/cloudnative-pg --namespace cdc-test
```
Then create a `Cluster` CR with `wal_level = logical` and publication already enabled (I’ll provide the exact manifest).

### 3. MySQL
**Best:** Percona Operator for MySQL or Bitnami Helm chart (both support ROW binlog out of the box).

```bash
helm repo add bitnami https://charts.bitnami.com/bitnami
helm install mysql-test bitnami/mysql --namespace cdc-test \
  --set auth.rootPassword=YourStrongPassword123! \
  --set primary.extraEnvVars[0].name=MYSQL_BINLOG_FORMAT \
  --set primary.extraEnvVars[0].value=ROW
```

### 4. SQL Server
**Best:** Microsoft’s official guidance + Helm (StatefulSet pattern is rock-solid for CDC).

Use the sample Helm chart from Microsoft or the simple StatefulSet:
```bash
helm repo add microsoft https://mssql-charts.storage.googleapis.com/
# or use the official quickstart StatefulSet YAML
```
CDC enablement is just `EXEC sys.sp_cdc_enable_db;` + table-level — same as always.

### 5. Db2
**Best:** IBM Db2U Next Gen operator (now Helm-based in 2026).

You’ll request the official `db2-operator` Helm tarball from IBM Support (standard for enterprise customers). Once you have it:
```bash
helm install db2-operator ./db2-operator -f overrides.yaml --namespace cdc-test
```
For pure dev/testing you can also use the community `ibmcom/db2` image in a StatefulSet.