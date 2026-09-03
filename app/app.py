"""
Delta Time Machine — workshop Streamlit app for Databricks Apps.

Reads the trips table built in notebooks 01 and 02, and lets you scrub through
its Delta version history to watch the data change.
"""

import os

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

TABLE = os.getenv("WORKSHOP_TABLE", "workspace.delta_workshop.trips")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")

st.set_page_config(page_title="Delta Time Machine", page_icon="🕰", layout="wide")


# --------------------------------------------------------------------------
# Connection
# --------------------------------------------------------------------------
# On Databricks Apps, Config() picks up the app's own service principal
# credentials automatically. Locally it falls back to your ~/.databrickscfg.


@st.cache_resource
def get_connection():
    if not WAREHOUSE_ID:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set. Attach a SQL warehouse to this "
            "app under Edit > Resources, or export the variable when running locally."
        )
    cfg = Config()
    return sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def run_query(query: str) -> pd.DataFrame:
    """Run a query, retrying once if the cached connection has gone stale.

    A warehouse that goes idle will drop the connection Streamlit is holding on
    to. Without this retry the app looks broken when it is only asleep.
    """
    try:
        with get_connection().cursor() as cur:
            cur.execute(query)
            return cur.fetchall_arrow().to_pandas()
    except Exception:
        get_connection.clear()
        with get_connection().cursor() as cur:
            cur.execute(query)
            return cur.fetchall_arrow().to_pandas()


@st.cache_data(ttl=60)
def load_history() -> pd.DataFrame:
    df = run_query(f"DESCRIBE HISTORY {TABLE}")
    return df[["version", "timestamp", "operation"]].sort_values(
        "version", ascending=False
    )


@st.cache_data(ttl=60)
def load_snapshot(version: int) -> pd.DataFrame:
    return run_query(f"""
        SELECT
            count(*)                        AS row_count,
            round(avg(fare_amount), 2)      AS avg_fare,
            round(avg(trip_distance), 2)    AS avg_distance,
            round(min(fare_amount), 2)      AS min_fare
        FROM {TABLE} VERSION AS OF {version}
    """)


@st.cache_data(ttl=60)
def load_rows(version: int, limit: int) -> pd.DataFrame:
    return run_query(f"SELECT * FROM {TABLE} VERSION AS OF {version} LIMIT {limit}")


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

st.title("Delta Time Machine")
st.caption(f"Reading `{TABLE}` — every version below is a commit you made in notebook 02.")

try:
    history = load_history()
except Exception as e:
    st.error("Could not read the table history.")
    st.code(str(e))
    st.info(
        "Checklist: the app has a SQL warehouse attached under Resources, the "
        "warehouse is running, and the app's service principal has SELECT on the "
        "table and CAN USE on the warehouse."
    )
    st.stop()

versions = history["version"].tolist()
latest = max(versions)

left, right = st.columns([1, 2], gap="large")

with left:
    st.subheader("Pick a version")
    selected = st.select_slider(
        "Table version",
        options=sorted(versions),
        value=latest,
        help="Delta keeps every commit queryable. Slide back to read the past.",
    )
    row = history.loc[history["version"] == selected].iloc[0]
    st.metric("Operation that produced it", row["operation"])
    st.caption(f"Committed {row['timestamp']}")

with right:
    st.subheader(f"The table at version {selected}")
    stats = load_snapshot(selected).iloc[0]
    current = load_snapshot(latest).iloc[0]

    a, b, c, d = st.columns(4)
    a.metric(
        "Rows",
        f"{int(stats['row_count']):,}",
        delta=int(stats["row_count"] - current["row_count"]) or None,
        help="Difference shown against the latest version",
    )
    b.metric("Average fare", f"${stats['avg_fare']:.2f}")
    c.metric("Average distance", f"{stats['avg_distance']:.2f} mi")
    d.metric("Minimum fare", f"${stats['min_fare']:.2f}")

st.divider()

limit = st.slider("Rows to fetch", 10, 500, 50, step=10)

tab_rows, tab_history, tab_sql = st.tabs(["Rows", "Full history", "The query"])

with tab_rows:
    st.dataframe(load_rows(selected, limit), use_container_width=True, hide_index=True)

with tab_history:
    st.dataframe(history, use_container_width=True, hide_index=True)
    st.caption(
        "This is the Delta transaction log, surfaced through DESCRIBE HISTORY. "
        "Nothing here was designed by us — it is a byproduct of how Delta commits."
    )

with tab_sql:
    st.code(
        f"SELECT * FROM {TABLE} VERSION AS OF {selected} LIMIT {limit}",
        language="sql",
    )
    st.caption(
        "Two extra words — VERSION AS OF — are the entire difference between "
        "reading the present and reading the past."
    )
