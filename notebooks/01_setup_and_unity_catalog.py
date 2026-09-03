# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Setup and Unity Catalog
# MAGIC
# MAGIC **Time: ~10 minutes**
# MAGIC
# MAGIC By the end of this notebook you will have one table that the rest of the
# MAGIC workshop builds on. Everything else we do today happens to this table.
# MAGIC
# MAGIC Run each cell with `Shift + Enter`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Where does data live?
# MAGIC
# MAGIC Databricks addresses every table with three parts:
# MAGIC
# MAGIC ```
# MAGIC catalog . schema . table
# MAGIC ```
# MAGIC
# MAGIC A **catalog** is the top-level container. A **schema** groups related tables
# MAGIC inside it. This is Unity Catalog, and it is how permissions, lineage, and
# MAGIC discovery all work.
# MAGIC
# MAGIC Free Edition gives you one catalog named `workspace` to start with.

# COMMAND ----------

CATALOG = "workspace"
SCHEMA = "delta_workshop"
TABLE = "trips"

FQN = f"{CATALOG}.{SCHEMA}.{TABLE}"
print(f"Everything today happens to: {FQN}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Create your schema
# MAGIC
# MAGIC We use the existing `workspace` catalog because creating a new catalog needs
# MAGIC admin rights that not every attendee will have. If you are a workspace admin
# MAGIC and want to see catalog creation, the commented line below does it.

# COMMAND ----------

# spark.sql("CREATE CATALOG IF NOT EXISTS workshop")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"USE {CATALOG}.{SCHEMA}")
print(f"Using {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Land some data
# MAGIC
# MAGIC Databricks ships a read-only `samples` catalog, so nobody has to upload a
# MAGIC file. We take a small slice of the NYC taxi dataset.
# MAGIC
# MAGIC If `samples` is unavailable in your workspace, the fallback below generates
# MAGIC equivalent synthetic rows so the workshop still runs.

# COMMAND ----------

source_ok = False
try:
    spark.sql("SELECT 1 FROM samples.nyctaxi.trips LIMIT 1").collect()
    source_ok = True
    print("samples.nyctaxi.trips is available")
except Exception as e:
    print(f"samples catalog unavailable, using synthetic data instead:\n  {e}")

# COMMAND ----------

if source_ok:
    spark.sql(f"""
        CREATE OR REPLACE TABLE {FQN} AS
        SELECT
            tpep_pickup_datetime  AS pickup_at,
            tpep_dropoff_datetime AS dropoff_at,
            trip_distance,
            fare_amount,
            pickup_zip,
            dropoff_zip
        FROM samples.nyctaxi.trips
        LIMIT 5000
    """)
else:
    from pyspark.sql import functions as F

    df = (
        spark.range(5000)
        .withColumn("pickup_at", F.expr("timestamp('2024-01-01') + make_dt_interval(0, 0, 0, id % 100000)"))
        .withColumn("dropoff_at", F.expr("pickup_at + make_dt_interval(0, 0, 0, 300 + (id % 2400))"))
        .withColumn("trip_distance", F.round(F.rand(42) * 20 + 0.3, 2))
        .withColumn("fare_amount", F.round(F.col("trip_distance") * 3.1 + 2.5, 2))
        .withColumn("pickup_zip", (10001 + F.col("id") % 180).cast("int"))
        .withColumn("dropoff_zip", (10001 + F.col("id") % 173).cast("int"))
        .drop("id")
    )
    df.write.mode("overwrite").saveAsTable(FQN)

print(f"Created {FQN}")

# COMMAND ----------

display(spark.table(FQN).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Find it in the UI
# MAGIC
# MAGIC Open **Catalog** in the left sidebar and click down through
# MAGIC `workspace` → `delta_workshop` → `trips`.
# MAGIC
# MAGIC Look at the **Sample data**, **Details**, and **Permissions** tabs. That
# MAGIC Permissions tab matters later: the Streamlit app runs as its own identity and
# MAGIC will need `SELECT` granted here.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC **You now have a table. Continue to notebook 02.**
