# Databricks in Two Hours

A hands-on, self-contained workshop for people who are new to Databricks. You
build a Delta table, explore how Delta Lake works, and deploy a Streamlit app —
the **Delta Time Machine** — that reads the table's version history and lets you
scrub back through every change you made. It runs entirely on Databricks Free
Edition.

```
notebooks/01_setup_and_unity_catalog.py   Unity Catalog + build the table
notebooks/02_delta_lake_concepts.py       Delta Lake, six ideas
app/app.py                                Delta Time Machine (Streamlit)
app/app.yaml                              Databricks Apps config
app/requirements.txt                      Python dependencies
slides/delta_table_anatomy.svg            Diagram for the Delta explanation
```

---

## Before you start

1. Sign up for [Databricks Free Edition](https://www.databricks.com/learn/free-edition).
   Sign in with email OTP, Google, or Microsoft — there is no SSO.
2. Log in once and confirm you reach a workspace.
3. You only need a browser. There is nothing to install locally.

Free Edition allows **one Databricks App per account**, so use your own account.
There is no shared-workspace option.

Expect the whole workshop to take about two hours end to end. Compute
provisioning for the app is the least predictable step, so leave yourself some
slack near the finish.

---

## 1. Get the code into your workspace

Use a Git folder — nothing to install.

1. In the workspace sidebar: **Workspace → Create → Git folder**
2. Paste this repository's HTTPS URL and clone it
3. The notebooks open directly from the Git folder as real notebooks with cells
   (they are stored in Databricks source format, not as flat scripts)

If you cloned earlier and the layout looks different, open the Git folder's git
menu and **Pull** to get the latest `notebooks/`, `app/`, and `slides/` folders.

---

## 2. Unity Catalog and building the table

Open `notebooks/01_setup_and_unity_catalog.py` and run it top to bottom
(`Shift + Enter` per cell). It takes about ten minutes and leaves you with one
table that the rest of the workshop builds on:

```
workspace.delta_workshop.trips
```

Along the way it introduces Unity Catalog's three-level namespace
(`catalog.schema.table`), creates the schema, and lands a slice of the NYC taxi
sample data. If the `samples` catalog is unavailable in your workspace, the
notebook automatically generates equivalent synthetic rows so the workshop still
runs.

When it finishes, open **Catalog** in the sidebar and click down through
`workspace → delta_workshop → trips` to see it in the UI. Note the
**Permissions** tab — it matters later, because the app runs as its own identity
and will need `SELECT` on this table.

---

## 3. Delta Lake concepts

Open `slides/delta_table_anatomy.svg` first and look at it before running any
code. The whole section lands once you accept one idea: **a Delta table is
Parquet files plus an ordered log of commits, and the log decides which files
count.**

Then run `notebooks/02_delta_lake_concepts.py` top to bottom. It walks through
six ideas, each of which adds a new version to the table's history:

1. **What a Delta table is** — `DESCRIBE DETAIL`
2. **It behaves like a table** — `UPDATE`, `DELETE`
3. **Every change is a version** — `DESCRIBE HISTORY`
4. **Time travel** — `VERSION AS OF 0` versus now
5. **MERGE** — the upsert real pipelines run on
6. **Schema enforcement, then evolution** — a write that is *rejected* on
   purpose, then the same write with `mergeSchema`

Two things to expect so they don't surprise you:

- **Section 6's first write is supposed to fail.** It tries to append a column
  the table has never seen, and Delta rejects it with a
  `DELTA_METADATA_MISMATCH`. That rejection is the point — the cell catches it
  and prints "Rejected, as intended." The very next cell repeats the write with
  `mergeSchema` enabled, which succeeds and backfills `NULL` for existing rows.
- **Leave `RESTORE` alone.** Section 4 mentions it but keeps it commented. You
  want the deletions to stay visible in the app at the end.

By the end, that version history is exactly what the app reads. Note the final
version number the last cell prints.

---

## 4. Deploy the Delta Time Machine app

The app compute takes a few minutes to start, so begin this step before you need
the result.

1. **Compute → Apps → Create app**
2. Choose **Custom**, name it `delta-time-machine`, and create it
3. Wait for the app compute to reach **Running** — this is the slow step
4. Under **Edit → Resources**, add your **SQL warehouse**. **Set the resource key
   to exactly `sql-warehouse`** — `app.yaml` reads the warehouse ID from that key
5. Give the resource **CAN USE** permission
6. Click **Deploy**, browse into your Git folder, and select the **`app`**
   folder (the one containing `app.py` and `app.yaml` — not the repo root)
7. Open the app URL

Free Edition gives you one 2X-Small SQL warehouse. If it is asleep, start it
manually first, or the app's first query will hang.

### Grant the app access to the table

The app runs as its own service principal, not as you. Without read access it
loads and immediately shows an error. Open the app's **Authorization** page, copy
its service principal ID, and run this in a notebook:

```sql
GRANT USE CATALOG ON CATALOG workspace TO `<service-principal-id>`;
GRANT USE SCHEMA ON SCHEMA workspace.delta_workshop TO `<service-principal-id>`;
GRANT SELECT ON TABLE workspace.delta_workshop.trips TO `<service-principal-id>`;
```

This is the single most common reason the app fails at the finish line.

---

## 5. The payoff

Open the app and scrub the version slider. Each version is one of the commits
you made in notebook 02 — watch the row count, average fare, and other metrics
change as you move between `CREATE`, `UPDATE`, `DELETE`, `MERGE`, and the
`mergeSchema` write. The "Full history" tab is the Delta transaction log, and the
"The query" tab shows that the only difference between reading the present and
the past is two words: `VERSION AS OF`.

---

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `App creation failed unexpectedly` | Known intermittent Free Edition backend issue, not your code. Delete the app and retry once. |
| App shows a permissions error on load | The service principal grants were not applied. Run the `GRANT` block above with the correct SP ID. |
| `DATABRICKS_WAREHOUSE_ID is not set` | The warehouse resource is missing, or its key is not exactly `sql-warehouse`. |
| Deploy can't find `app.yaml` | You selected the repo root instead of the `app` folder. Redo step 6 and pick `app`. |
| First query hangs | The warehouse is asleep. Start it manually and retry. |
| `PERSIST TABLE is not supported on serverless compute` | Serverless rejects `.cache()`/`.persist()`. The notebook already avoids this; if you edited a cell, remove the `.cache()` call. |
| Compute stops mid-session | Fair-usage quota exceeded — compute is unavailable for the rest of the day. Your data is not deleted. |
| `samples.nyctaxi.trips` not found | Expected on some workspaces. Notebook 01 detects this and generates synthetic rows automatically. |

---

## Limits worth knowing

- Apps stop automatically 24 hours after being started or redeployed. You can
  restart them, but an app will not still be running untouched next week.
- Outbound internet from the app is restricted to a limited set of trusted
  domains, so it cannot call an arbitrary external API.
- The versions in `app/requirements.txt` are pinned deliberately. Leave them
  alone unless you have a reason to change them.
- Free Edition is for personal, non-commercial use. If you are running this as
  internal company training, check that framing against the terms first — a paid
  trial workspace may be more appropriate.
