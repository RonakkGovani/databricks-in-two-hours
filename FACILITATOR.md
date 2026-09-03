# Facilitator runbook

For the person running "Databricks in Two Hours" as a live session. Attendees
follow [`README.md`](README.md); this file is the logistics and teaching layer on
top of it.

---

## Send this to attendees 48 hours ahead

Not optional. Account creation during the session will cost you 20 minutes.

> 1. Sign up for Databricks Free Edition at https://www.databricks.com/learn/free-edition
>    (email OTP, Google, or Microsoft sign-in — there is no SSO)
> 2. Log in once and confirm you reach a workspace
> 3. Bring a laptop with a browser. Nothing to install.

Free Edition allows **one Databricks App per account**, so everyone needs their
own account. There is no shared-workspace option.

Also send them this repository's clone URL so they can create the Git folder at
the start of the session.

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

## The Delta block (0:20–0:50)

Put `slides/delta_table_anatomy.svg` on screen *before* running anything. The
whole block lands if they accept one idea first: a Delta table is Parquet files
plus an ordered log of commits, and the log decides which files count.

Then run notebook 02 in order. Name and skip: `OPTIMIZE`, liquid clustering,
`VACUUM`, change data feed. The only one worth a spoken sentence is `VACUUM`,
because it is what eventually ends time travel.

**Do not** try to reveal `_delta_log` with `dbutils.fs.ls`. On managed Unity
Catalog tables the storage path is not reliably browsable, and it fails ugly in
front of an audience. The diagram does that job.

**Do not** run `RESTORE`. You want the deletions still visible in the app.

Section 6's schema-enforcement cell is *supposed* to fail with a rejected-write
message. If it fails with any *other* error, stop and debug before moving on.

---

## Deploying the app (0:50–1:30)

The mechanical steps are in the README. The two that most often go wrong:

- The SQL warehouse resource key must be exactly `sql-warehouse`, or the app
  cannot find the warehouse ID.
- The service-principal `GRANT` block is the single most common reason the app
  fails at the finish line. Budget five minutes for it and put the SQL on a
  slide.

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

If the dry run passes, leave `app/requirements.txt` pinned as-is until after the
session — an upstream Streamlit release the week of your workshop is not a
variable you want.

---

## Fallback

If app compute will not provision (a known intermittent Free Edition issue) or
the fair-usage quota is exhausted, switch to your screen recording. Do not spend
session time fighting backend provisioning.
