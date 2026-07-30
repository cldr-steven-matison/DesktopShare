# Get Started with Cloudera AI Workbench

> **Your build:** `2.0.56-h3000-b120`
> Cloudera AI Workbench is the workspace formerly known as **Cloudera Machine Learning (CML)**. It's a cloud-native platform for the full ML lifecycle — explore data, run notebooks, train and track experiments, deploy models as REST endpoints, schedule jobs, and host apps — all in one place.

---

## 1. Key concepts (the mental model)

| Concept | What it is |
|---|---|
| **Workbench** | The provisioned environment you're logged into. It maps to compute (CPU/GPU) and connects to your enterprise data. |
| **Project** | The unit of work. Holds your files, code, dependencies, and settings. Backed by a Git repo or blank/template. Where collaboration happens. |
| **Session** | An interactive, running compute environment inside a project (JupyterLab / Workbench editor / VS Code). This is where you write and run code live. |
| **ML Runtime** | The container image that backs a session/job — defines the editor, kernel (Python/R/Scala), and whether it's CPU or GPU. You pick one when you start a session. |
| **Experiment** | A tracked training run (params, metrics, artifacts) so you can compare model variations. |
| **Model** | A function deployed as a REST endpoint, with lineage and monitoring. |
| **Job** | A scheduled or triggered script run — pipelines, retraining, batch scoring. |
| **Application** | A long-running interactive app (Flask, Streamlit, Dash, etc.) served from your project. |

---

## 2. First 15 minutes — a quick path

### Step 1 — Create a Project
1. From the Workbench home, click **Projects → New Project**.
2. Give it a name and choose the initial files source:
   - **Blank** — start empty.
   - **Template** — Cloudera-provided starter (Python, R, etc.).
   - **Git** — clone from a repo URL (recommended for real work; keeps you in version control).
   - **Local files** — upload a folder/zip.
3. (Optional) Set the project to **Team** ownership to collaborate; otherwise it's personal.
4. Create.

### Step 2 — Start a Session
1. Inside the project, click **New Session**.
2. Choose:
   - **Editor** — JupyterLab (notebooks), Workbench (script + console), or VS Code if available.
   - **Kernel / Runtime** — e.g. *Python 3.x*, CPU or **GPU** variant.
   - **Resource profile** — vCPU / memory / GPU count.
3. Launch. You now have a live terminal + editor connected to your data.

### Step 3 — Run your first code
In the session console or a notebook cell:
```python
print("Hello from Cloudera AI Workbench")
import sys; print(sys.version)
```
Open a **Terminal** (in the session) to use `git`, `pip`, and shell tools directly.

### Step 4 — Install dependencies
```bash
pip install -r requirements.txt      # if your project has one
# or
pip install pandas scikit-learn
```
> Tip: put dependencies in `requirements.txt` (or a `cdsw-build.sh` / build script) so sessions, jobs, and models install them reproducibly.

---

## 3. Going further

### Track an Experiment
Use MLflow-style tracking to log params/metrics:
```python
import mlflow
with mlflow.start_run():
    mlflow.log_param("lr", 0.01)
    mlflow.log_metric("rmse", 0.42)
    # mlflow.sklearn.log_model(model, "model")
```
Compare runs under the project's **Experiments** tab.

### Deploy a Model (REST endpoint)
1. Write an entry function in a file, e.g. `predict.py`:
   ```python
   def predict(args):
       # args is a dict from the JSON request
       return {"result": args["x"] * 2}
   ```
2. **Models → New Model** → point it at `predict.py` and the `predict` function.
3. Pick runtime + resources, deploy. You get a REST URL + access key.
4. Test:
   ```bash
   curl -H "Content-Type: application/json" \
        -d '{"accessKey":"<KEY>","request":{"x":21}}' \
        <MODEL_ENDPOINT_URL>
   ```

### Schedule a Job
- **Jobs → New Job** → select a script, set a schedule (cron) or manual/dependent trigger, choose runtime + resources. Good for retraining, ETL, batch scoring.

### Host an Application
- **Applications → New Application** → point at a script that starts a web server (Flask/Streamlit/Dash) on the expected port. Cloudera serves it at a stable subdomain.

---

## 4. Working with data

- Sessions connect to enterprise data sources configured for the Workbench (data lakes, warehouses, object storage).
- Use the built-in **Data Connections** / Spark data connections to query without hardcoding credentials.
- For exploratory work: connect to a data source, run SQL, and use the drag-and-drop visualization tooling before you write model code.

---

## 5. Collaboration & good habits

- **Use Git** for project code — commit from the session terminal; treat the project workspace like any repo.
- **Pin dependencies** in `requirements.txt` so runtimes are reproducible across sessions/jobs/models.
- **Stop idle sessions** — they hold compute. Sessions are for interactive work; move recurring work into Jobs.
- **Right-size runtimes** — only request a GPU runtime when you actually need it.
- **Share via Team projects** and control access with roles.

---

## 6. Official documentation

- **Product hub:** https://docs.cloudera.com/machine-learning/cloud/index.html
- **Overview:** https://docs.cloudera.com/machine-learning/cloud/product/topics/ml-product-overview.html
- The docs portal is search-driven — use in-page **Search** for the exact topics: `Projects`, `Sessions`, `ML Runtimes`, `Experiments`, `Models`, `Jobs`, `Applications`, `Data Connections`.

> **Version note:** Your build is `2.0.56-h3000-b120`. If a documented feature or menu differs from what you see, confirm the docs version selector matches your Workbench release, since UI labels shift between versions.

---

## Quick reference — where things live in the UI

```
Workbench
 └─ Projects
     └─ <your project>
         ├─ Files        (code, notebooks, requirements.txt)
         ├─ Sessions     (interactive JupyterLab / Workbench / VS Code)
         ├─ Experiments  (tracked training runs)
         ├─ Models       (deployed REST endpoints)
         ├─ Jobs         (scheduled / triggered scripts)
         ├─ Applications (hosted web apps)
         └─ Settings     (runtimes, team access, env vars)
```
