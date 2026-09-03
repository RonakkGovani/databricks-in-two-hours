# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Delta Lake, through one table
# MAGIC
# MAGIC **Time: ~30 minutes**
# MAGIC
# MAGIC Six ideas, in order. Each one operates on the `trips` table you just built,
# MAGIC and each one adds a version to its history. By the end, that history is what
# MAGIC your Streamlit app will read.
# MAGIC
# MAGIC 1. What a Delta table actually is
# MAGIC 2. It behaves like a database table
# MAGIC 3. Every change is a version
# MAGIC 4. Time travel
# MAGIC 5. MERGE, the upsert
# MAGIC 6. Schema enforcement, then evolution

# COMMAND ----------

CATALOG = "workspace"
SCHEMA = "delta_workshop"
TABLE = "trips"
FQN = f"{CATALOG}.{SCHEMA}.{TABLE}"

spark.sql(f"USE {CATALOG}.{SCHEMA}")
print(FQN)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. What a Delta table actually is
# MAGIC
# MAGIC Two things, sitting in cloud storage:
# MAGIC
# MAGIC - **Parquet files** holding the rows. Columnar, compressed, nothing exotic.
# MAGIC - **A transaction log** — an ordered list of commits describing which files
# MAGIC   belong to the table right now.
# MAGIC
# MAGIC That second part is the whole trick. Nothing is edited in place. To delete
# MAGIC rows, Delta writes new files without them and commits "stop using file A,
# MAGIC start using file B." Readers follow the log, so they always see one
# MAGIC consistent set of files, never a half-finished write.
# MAGIC
# MAGIC Everything below is a consequence of that one design.

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE DETAIL workspace.delta_workshop.trips

# COMMAND ----------

# MAGIC %md
# MAGIC Note `format` = `delta`, plus `numFiles` and `sizeInBytes`. A plain folder of
# MAGIC Parquet files has no equivalent of what comes next.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. It behaves like a database table
# MAGIC
# MAGIC If your background is files on a data lake — CSV or Parquet in blob storage —
# MAGIC then `UPDATE` and `DELETE` were never available to you. You rewrote the whole
# MAGIC dataset and hoped no one was reading it mid-job.
# MAGIC
# MAGIC Here they just work, one row at a time, transactionally.

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS total_rows FROM workspace.delta_workshop.trips

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Apply a $3.00 minimum fare. This will match rows, so it commits a version.
# MAGIC UPDATE workspace.delta_workshop.trips
# MAGIC SET fare_amount = 3.00
# MAGIC WHERE fare_amount < 3.00

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Drop the obviously broken rows
# MAGIC DELETE FROM workspace.delta_workshop.trips
# MAGIC WHERE trip_distance <= 0

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT count(*) AS total_rows FROM workspace.delta_workshop.trips

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Every change is a version
# MAGIC
# MAGIC The log is not an internal detail you have to take on faith. You can read it.

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY workspace.delta_workshop.trips

# COMMAND ----------

# MAGIC %md
# MAGIC One row per commit. Look at the `version`, `operation`, and
# MAGIC `operationMetrics` columns — the `CREATE OR REPLACE TABLE AS SELECT`, then the
# MAGIC `UPDATE`, then the `DELETE`, with row counts for each.
# MAGIC
# MAGIC This is an audit trail you got for free, without designing one.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Time travel
# MAGIC
# MAGIC Because old files are still referenced by old log entries, previous versions
# MAGIC of the table are still queryable. You do not need a backup to answer "what did
# MAGIC this look like before I broke it?"

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT
# MAGIC     (SELECT count(*) FROM workspace.delta_workshop.trips VERSION AS OF 0) AS at_version_0,
# MAGIC     (SELECT count(*) FROM workspace.delta_workshop.trips)                 AS right_now

# COMMAND ----------

# MAGIC %md
# MAGIC You can also travel by timestamp:
# MAGIC
# MAGIC ```sql
# MAGIC SELECT * FROM workspace.delta_workshop.trips TIMESTAMP AS OF '2026-09-03T09:00:00';
# MAGIC ```
# MAGIC
# MAGIC And you can undo a mistake by restoring:
# MAGIC
# MAGIC ```sql
# MAGIC RESTORE TABLE workspace.delta_workshop.trips VERSION AS OF 0;
# MAGIC ```
# MAGIC
# MAGIC Leave `RESTORE` commented out — we want the deletions to stay visible in the
# MAGIC app at the end. Mention it, don't run it.

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. MERGE, the upsert
# MAGIC
# MAGIC This is the operation real pipelines are built on. A batch of incoming
# MAGIC records arrives; some are corrections to rows you already have, some are new.
# MAGIC `MERGE` handles both in a single atomic statement.
# MAGIC
# MAGIC First, a small batch of updates arriving from "upstream":

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Two kinds of record in one batch:
# MAGIC --   corrections to trips we already have  -> will MATCH
# MAGIC --   trips we have never seen              -> will NOT MATCH
# MAGIC --
# MAGIC -- The GROUP BY is not decoration. MERGE fails if two source rows compete to
# MAGIC -- update the same target row, so the batch must be unique on the match key.
# MAGIC CREATE OR REPLACE TEMP VIEW incoming_trips AS
# MAGIC WITH sample AS (
# MAGIC     SELECT * FROM workspace.delta_workshop.trips LIMIT 200
# MAGIC ),
# MAGIC corrections AS (
# MAGIC     SELECT
# MAGIC         pickup_at,
# MAGIC         pickup_zip,
# MAGIC         max(dropoff_at)          AS dropoff_at,
# MAGIC         max(trip_distance)       AS trip_distance,
# MAGIC         max(fare_amount) + 5.00  AS fare_amount,   -- a $5 fare correction
# MAGIC         max(dropoff_zip)         AS dropoff_zip
# MAGIC     FROM sample
# MAGIC     GROUP BY pickup_at, pickup_zip
# MAGIC ),
# MAGIC brand_new AS (
# MAGIC     SELECT
# MAGIC         timestamp('2030-01-01 08:00:00') AS pickup_at,
# MAGIC         99001                            AS pickup_zip,
# MAGIC         timestamp('2030-01-01 08:24:00') AS dropoff_at,
# MAGIC         7.4                              AS trip_distance,
# MAGIC         31.50                            AS fare_amount,
# MAGIC         99002                            AS dropoff_zip
# MAGIC     UNION ALL
# MAGIC     SELECT
# MAGIC         timestamp('2030-01-01 09:15:00'),
# MAGIC         99003,
# MAGIC         timestamp('2030-01-01 09:31:00'),
# MAGIC         3.1,
# MAGIC         14.00,
# MAGIC         99004
# MAGIC )
# MAGIC SELECT pickup_at, dropoff_at, trip_distance, fare_amount, pickup_zip, dropoff_zip FROM corrections
# MAGIC UNION ALL
# MAGIC SELECT pickup_at, dropoff_at, trip_distance, fare_amount, pickup_zip, dropoff_zip FROM brand_new;
# MAGIC
# MAGIC SELECT count(*) AS incoming_records FROM incoming_trips

# COMMAND ----------

# MAGIC %sql
# MAGIC MERGE INTO workspace.delta_workshop.trips AS target
# MAGIC USING incoming_trips AS source
# MAGIC   ON  target.pickup_at  = source.pickup_at
# MAGIC   AND target.pickup_zip = source.pickup_zip
# MAGIC WHEN MATCHED THEN
# MAGIC   UPDATE SET target.fare_amount = source.fare_amount
# MAGIC WHEN NOT MATCHED THEN
# MAGIC   INSERT *

# COMMAND ----------

# MAGIC %md
# MAGIC Read the result metrics: `num_updated_rows` and `num_inserted_rows`. Both
# MAGIC branches fired — the corrections updated existing trips, the two 2030 trips
# MAGIC were inserted. One statement, one atomic commit, no staging table.
# MAGIC
# MAGIC Then check the history again: there is a new version, labelled `MERGE`.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- The newest commit is the top row
# MAGIC DESCRIBE HISTORY workspace.delta_workshop.trips

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Schema enforcement, then evolution
# MAGIC
# MAGIC Two concepts, one demo.
# MAGIC
# MAGIC A Delta table knows its own schema and defends it. Try to append data with an
# MAGIC extra column and the write is **rejected** — you do not silently end up with a
# MAGIC corrupted table. This cell is *supposed* to fail.

# COMMAND ----------

from pyspark.sql import functions as F

# .cache() + .count() forces this batch into memory now, so the append below is
# not reading the same table it is writing to.
extra = (
    spark.table(FQN)
    .limit(50)
    .withColumn("payment_type", F.lit("card"))   # a column the table has never seen
    .cache()
)
print(f"{extra.count()} rows staged, with an extra column")

try:
    extra.write.mode("append").saveAsTable(FQN)
    print("Appended — unexpected!")
except Exception as e:
    print("Rejected, as intended. Delta refused the mismatched schema:\n")
    print(str(e)[:600])

# COMMAND ----------

# MAGIC %md
# MAGIC Now the same write, with explicit consent. `mergeSchema` says "I meant to add
# MAGIC that column." Delta widens the schema and backfills `NULL` for existing rows.
# MAGIC
# MAGIC The point: schema changes are possible, but never accidental.

# COMMAND ----------

extra.write.mode("append").option("mergeSchema", "true").saveAsTable(FQN)

display(
    spark.table(FQN)
    .groupBy("payment_type")
    .count()
    .orderBy(F.col("count").desc())
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Mentioned, not demoed
# MAGIC
# MAGIC Name these and move on — they matter in production, but they are not what a
# MAGIC first two hours should spend minutes on:
# MAGIC
# MAGIC | Command | What it is for |
# MAGIC | --- | --- |
# MAGIC | `OPTIMIZE` | Compacts many small files into fewer large ones |
# MAGIC | `CLUSTER BY` (liquid clustering) | Physically co-locates rows you filter on |
# MAGIC | `VACUUM` | Deletes old unreferenced files. **This is what ends time travel** |
# MAGIC | Change data feed | Streams the row-level changes out to consumers |
# MAGIC
# MAGIC The one worth a sentence out loud is `VACUUM`: time travel is not infinite,
# MAGIC it lasts as long as the old files are retained.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Note your final version number
# MAGIC
# MAGIC Run this and keep the number visible. The app in the next section reads this
# MAGIC same history.

# COMMAND ----------

history = spark.sql(f"DESCRIBE HISTORY {FQN}")
display(history.select("version", "timestamp", "operation").orderBy("version"))

print(f"\nLatest version: {history.selectExpr('max(version)').collect()[0][0]}")
print(f"Table for the app: {FQN}")
