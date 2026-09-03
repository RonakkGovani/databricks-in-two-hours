"""
NYC Taxi Fleet Console — a dashboard + data-entry app for Databricks Apps.

Monitors recent trips from workspace.delta_workshop.trips and lets an operator
log a completed trip. The dashboard refreshes the moment a trip is logged.
Authenticates as the app's own service principal.
"""

import os

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config

TABLE = os.getenv("WORKSHOP_TABLE", "workspace.delta_workshop.trips")
WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")

st.set_page_config(page_title="NYC Taxi Fleet Console", page_icon="🚕", layout="wide")


# --------------------------------------------------------------------------
# Connection + SQL helpers — the app's service principal, picked up by Config().
# --------------------------------------------------------------------------
@st.cache_resource
def get_connection():
    if not WAREHOUSE_ID:
        raise RuntimeError(
            "DATABRICKS_WAREHOUSE_ID is not set. Attach a SQL warehouse under "
            "Edit > Resources, or export the variable when running locally."
        )
    cfg = Config()
    return sql.connect(
        server_hostname=cfg.host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=lambda: cfg.authenticate,
    )


def _execute(query: str, read: bool):
    """Run one statement, retrying once if the pooled connection went stale."""

    def once():
        with get_connection().cursor() as cur:
            cur.execute(query)
            if read:
                return cur.fetchall_arrow().to_pandas()
            try:  # DML returns a small metrics row; tolerate none
                return cur.fetchall_arrow().to_pandas()
            except Exception:
                return None

    try:
        return once()
    except Exception:
        get_connection.clear()
        return once()


def run_query(query: str) -> pd.DataFrame:
    return _execute(query, read=True)


def run_write(query: str):
    result = _execute(query, read=False)
    if result is not None and not result.empty:
        for col in ("num_affected_rows", "num_inserted_rows"):
            if col in result.columns:
                return int(result.iloc[0][col])
    return None


NUMERIC = ("int", "bigint", "smallint", "tinyint", "long", "double", "float", "decimal")


def is_numeric(dtype: str) -> bool:
    return any(dtype.startswith(n) for n in NUMERIC)


def sql_literal(value, data_type: str) -> str:
    """Render a Python value as a SQL literal, safely quoted for its column type."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "NULL"
    dt = data_type.lower()
    if is_numeric(dt):
        return str(value)
    if dt.startswith("boolean"):
        return "true" if bool(value) else "false"
    if dt.startswith("timestamp"):
        return f"TIMESTAMP '{value}'"
    if dt.startswith("date"):
        return f"DATE '{value}'"
    return "'" + str(value).replace("'", "''") + "'"


@st.cache_data(ttl=300)
def load_schema():
    """Column name + type. DESCRIBE appends metadata rows after a blank/'#' row."""
    df = run_query(f"DESCRIBE {TABLE}")
    cols = []
    for _, r in df.iterrows():
        name = str(r["col_name"]).strip()
        if name == "" or name.startswith("#"):
            break
        cols.append((name, str(r["data_type"]).strip().lower()))
    return cols


@st.cache_data(ttl=60)
def load_data(limit: int, order_col: str | None) -> pd.DataFrame:
    order = f"ORDER BY `{order_col}` DESC" if order_col else ""
    return run_query(f"SELECT * FROM {TABLE} {order} LIMIT {limit}")


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
st.title("🚕 NYC Taxi Fleet Console")
st.caption(
    f"Recent trip activity from `{TABLE}`. Log a completed trip and the dashboard "
    "updates instantly."
)

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

try:
    schema = load_schema()
except Exception as e:
    st.error("Could not read the table.")
    st.code(str(e))
    st.info(
        "Checklist: a SQL warehouse is attached under Resources, it is running, "
        f"and the app's service principal has SELECT and MODIFY on `{TABLE}`."
    )
    st.stop()

# Order by the pickup time when the table has one, so the newest trips (and any
# you just logged) sit at the top of the sample the dashboard reads.
pickup_ts = next((c for c, t in schema if "pickup" in c and t.startswith("timestamp")), None)

# ---- Sidebar: data size + filters + refresh -------------------------------
st.sidebar.header("Dashboard controls")
n = st.sidebar.slider("Trips to load", 500, 20000, 5000, step=500)
data = load_data(n, pickup_ts)

if st.sidebar.button("🔄 Refresh data"):
    load_data.clear()
    st.rerun()

view = data.copy()
for label, colname, unit in [("Fare amount", "fare_amount", "$"), ("Trip distance", "trip_distance", "mi")]:
    if colname in data.columns and len(data):
        vals = data[colname].dropna()
        if len(vals) and float(vals.min()) < float(vals.max()):
            lo, hi = float(vals.min()), float(vals.max())
            rng = st.sidebar.slider(f"{label} ({unit})", lo, hi, (lo, hi))
            view = view[(view[colname] >= rng[0]) & (view[colname] <= rng[1])]

st.sidebar.caption(f"Showing {len(view):,} of {len(data):,} loaded trips.")

# ---- The app action: log a completed trip (INSERT) ------------------------
with st.expander("➕ Log a completed trip", expanded=False):
    st.caption("Enter the trip details, then submit. The dashboard refreshes with the new trip on top.")
    with st.form("log_trip"):
        inputs = {}
        grid = st.columns(3)
        for i, (name, dtype) in enumerate(schema):
            box = grid[i % 3]
            label = f"{name} · {dtype}"
            if dtype.startswith(("int", "bigint", "smallint", "tinyint", "long")):
                inputs[name] = (box.number_input(label, value=0, step=1), dtype)
            elif dtype.startswith(("double", "float", "decimal")):
                inputs[name] = (box.number_input(label, value=0.0), dtype)
            elif dtype.startswith("timestamp"):
                inputs[name] = (box.text_input(label, value=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")), dtype)
            elif dtype.startswith("date"):
                inputs[name] = (box.text_input(label, value=pd.Timestamp.now().strftime("%Y-%m-%d")), dtype)
            elif dtype.startswith("boolean"):
                inputs[name] = (box.checkbox(label, value=False), dtype)
            else:
                inputs[name] = (box.text_input(label, value=""), dtype)
        submitted = st.form_submit_button("Log trip", type="primary")

    if submitted:
        col_names = ", ".join(f"`{c}`" for c in inputs)
        values = ", ".join(sql_literal(v, dt) for v, dt in inputs.values())
        insert_sql = f"INSERT INTO {TABLE} ({col_names}) VALUES ({values})"
        try:
            run_write(insert_sql)
            load_data.clear()
            st.session_state["flash"] = "Trip logged. It's at the top of the dashboard now."
            st.rerun()
        except Exception as e:
            st.error("Could not log the trip.")
            st.code(insert_sql, language="sql")
            st.code(str(e))

# ---- KPIs -----------------------------------------------------------------
st.subheader("Fleet at a glance")
k = st.columns(4)
k[0].metric("Trips", f"{len(view):,}")
if "fare_amount" in view.columns and len(view):
    k[1].metric("Average fare", f"${view['fare_amount'].mean():.2f}")
    k[2].metric("Total fares", f"${view['fare_amount'].sum():,.0f}")
if "trip_distance" in view.columns and len(view):
    k[3].metric("Average distance", f"{view['trip_distance'].mean():.2f} mi")

# ---- Charts ---------------------------------------------------------------
left, right = st.columns(2)

with left:
    if {"trip_distance", "fare_amount"}.issubset(view.columns) and len(view):
        st.markdown("**Fare vs. distance**")
        st.scatter_chart(view, x="trip_distance", y="fare_amount", height=320)

    if "fare_amount" in view.columns:
        fares = view["fare_amount"].dropna()
        if fares.nunique() > 1:
            st.markdown("**Fare distribution**")
            counts = pd.cut(fares, bins=12).value_counts().sort_index()
            counts.index = [f"${int(iv.left)}–{int(iv.right)}" for iv in counts.index]
            st.bar_chart(counts, height=280)

with right:
    if pickup_ts and pickup_ts in view.columns and len(view):
        st.markdown("**Trips by hour of day**")
        hours = pd.to_datetime(view[pickup_ts]).dt.hour.value_counts().sort_index()
        st.bar_chart(hours, height=320)

    if "pickup_zip" in view.columns and len(view):
        st.markdown("**Busiest pickup ZIPs**")
        top = view["pickup_zip"].value_counts().head(10).sort_values()
        top.index = top.index.astype(str)
        st.bar_chart(top, height=280)

# ---- Detail table ---------------------------------------------------------
st.subheader("Trip detail")
st.caption("Most recent trips first.")
st.dataframe(view, use_container_width=True, hide_index=True, height=360)
