# Databricks in Two Hours — facilitator runbook

A hands-on workshop for people who have never used Databricks. Runs entirely on
Databricks Free Edition. Attendees finish having built a Delta table and deployed
a Streamlit app that reads its version history.

```
notebooks/01_setup_and_unity_catalog.py   Unity Catalog + build the table
notebooks/02_delta_lake_concepts.py       The Delta block, six ideas
app/app.py                                Delta Time Machine (Streamlit)
app/app.yaml                              Databricks Apps config
app/requirements.txt                      Python dependencies
slides/delta_table_anatomy.svg            Diagram for the Delta explanation
```

---

## Send this to attendees 48 hours ahead

Not optional. Account creation during the session will cost you 20 minutes.

> 1. Sign up for Databricks Free Edition at https://www.databricks.com/learn/free-edition
>    (email OTP, Google, or Microsoft sign-in — there is no SSO)
> 2. Log in once and confirm you reach a workspace
> 3. Bring a laptop with a browser. Nothing to install.

Free Edition allows **one Databricks App per account**, so everyone needs their
own account. There is no shared-workspace option.

---

## Run of show

| Time | Segment | What you are doing |
| --- | --- | --- |
| 0:00–0:10 | Workspace tour | Sidebar, notebooks, Catalog, Compute. Serverless only — no cluster config to teach. |
| 0:10–0:20 | Unity Catalog | Notebook 01. Three-level namespace, create the schema, land `trips`. |
| 0:20–0:50 | Delta Lake | Notebook 02. Show the SVG diagram before running any code. |
| 0:50–1:30 | Build the app | Create app from template, swap in `app/`, attach warehouse, deploy. |
| 1:30–1:45 | The payoff | Scrub the version slider. Connect it back to the commits they made. |
| 1:45–2:00 | Buffer and next steps | Do not schedule anything here. |

The buffer is load-bearing. App compute provisioning is the least predictable
step in the whole session.

---

## Getting the code into their workspace

Git folders, not the CLI. Nobody installs anything.

1. Push this directory to a repo your attendees can reach
2. In the workspace: **Workspace → Create → Git folder**, paste the repo URL
3. Notebooks open directly from the Git folder

The `.py` notebooks are in Databricks source format, so they import as real
notebooks with cells, not as flat scripts.

---

## The Delta block (0:20–0:50)

Put `slides/delta_table_anatomy.svg` on screen *before* running anything. The
whole block lands if they accept one idea first: a Delta table is Parquet files
plus an ordered log of commits, and the log decides which files count.

Then run notebook 02 in order. Six ideas:

1. **What it is** — `DESCRIBE DETAIL`
2. **It behaves like a table** — `UPDATE`, `DELETE`
3. **Every change is a version** — `DESCRIBE HISTORY`
4. **Time travel** — `VERSION AS OF 0` vs now
5. **MERGE** — the upsert real pipelines run on
6. **Schema enforcement, then evolution** — a write that fails on purpose, then
   the same write with `mergeSchema`

Name and skip: `OPTIMIZE`, liquid clustering, `VACUUM`, change data feed. The
only one worth a spoken sentence is `VACUUM`, because it is what eventually ends
time travel.

**Do not** try to reveal `_delta_log` with `dbutils.fs.ls`. On managed Unity
Catalog tables the storage path is not reliably browsable, and it fails ugly in
front of an audience. The diagram does that job.

**Do not** run `RESTORE`. You want the deletions still visible in the app.

---

## Deploying the app (0:50–1:30)

1. **Compute → Apps → Create app**
2. Choose **Custom**, name it `delta-time-machine`, create
3. Wait for app compute to start — this is the slow step
4. Under **Edit → Resources**, add the SQL warehouse. **Set the resource key to
   `sql-warehouse`** — `app.yaml` reads the ID from that exact key
5. Give the resource **CAN USE** permission
6. Choose **Deploy**, navigate to your Git folder, select the `app/` folder
7. Open the app URL

### Grant the app access to the table

The app runs as its own service principal, not as the attendee. It needs read
access, or the app loads and immediately shows an error.

Run in a notebook, substituting the app's service principal from the app's
**Authorization** page:

```sql
GRANT USE CATALOG ON CATALOG workspace TO `<service-principal-id>`;
GRANT USE SCHEMA ON SCHEMA workspace.delta_workshop TO `<service-principal-id>`;
GRANT SELECT ON TABLE workspace.delta_workshop.trips TO `<service-principal-id>`;
```

This step is the single most common reason the app fails at the finish line.
Budget five minutes for it and put the SQL on a slide.

---

## Known failure modes

| Symptom | Cause and response |
| --- | --- |
| `Compute error — App creation failed unexpectedly` | Known intermittent Free Edition backend issue, not their code. Delete the app and retry once. If it recurs, fall back to your recording. |
| App shows a permissions error on load | Service principal grants not applied. Run the `GRANT` block above. |
| `DATABRICKS_WAREHOUSE_ID is not set` | The warehouse resource is missing or its key is not `sql-warehouse`. |
| Warehouse is asleep, first query hangs | Free Edition gets one 2X-Small warehouse. Start it manually before the session. |
| Compute stops entirely mid-session | Fair usage quota exceeded — compute is unavailable for the rest of the day. Data is not deleted. Nothing to do but switch to demo mode. |
| `samples.nyctaxi.trips` not found | Notebook 01 detects this and generates synthetic rows automatically. |

Two hard limits to state out loud so nobody is surprised later:

- Apps stop automatically 24 hours after being started or redeployed. They can
  restart them, but the app will not still be running next week untouched.
- Outbound internet is restricted to a limited set of trusted domains, so the
  app cannot call an arbitrary external API.

---

## Before the session — dry run

Do this on a **fresh** Free Edition account, not your own well-configured one.
Every gap in these instructions shows up on a clean account and nowhere else.

- [ ] Git folder clones
- [ ] Notebook 01 runs top to bottom
- [ ] Notebook 02 runs top to bottom, and the schema-enforcement cell in section 6
      fails with a rejected-write message rather than any other error
- [ ] `MERGE` reports both updated *and* inserted rows
- [ ] App creates, deploys, and loads
- [ ] Version slider changes the row count
- [ ] Screen recording captured as fallback

Versions in `app/requirements.txt` are pinned on purpose. If the dry run passes,
leave them alone until after the session — an upstream Streamlit release the week
of your workshop is not a variable you want.

---

## A note on Free Edition terms

Free Edition is for personal, non-commercial use. If this workshop is internal
company training, check that framing against the terms before you run it — a
paid trial workspace may be the more appropriate vehicle.
