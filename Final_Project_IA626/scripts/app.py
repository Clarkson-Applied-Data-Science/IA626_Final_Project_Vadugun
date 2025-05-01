# stramlit.py

import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

# ─── CONFIG ─────────────────────────────────────────────────────────
DB_USER = 'username'
DB_PASS = 'password'
DB_HOST = 'mysql.clarksonmsda.org'
DB_PORT = 3306
DB_NAME = 'vadugun_nyc_parking'

db_url = URL.create(
    drivername='mysql+pymysql',
    username=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME
)
engine = create_engine(db_url, echo=False)

# ─── LAYOUT ─────────────────────────────────────────────────────────
st.set_page_config(page_title="NYC Parking Violations Dashboard", layout="wide")
st.title("📊 NYC Parking & Camera Violations")

# ─── HELPER: LOAD CSV/DB ──────────────────────────────────────────────
@st.cache_data
def load_repeat_offenders():
    path = "dashboard/repeat_offenders.csv"
    if os.path.exists(path):
        return pd.read_csv(path)
    # fallback to DB table
    try:
        df = pd.read_sql("SELECT * FROM agg_repeat_offenders", engine)
        return df
    except:
        return pd.DataFrame()

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────
st.sidebar.header("Filters")
# allow user to pick which prebuilt chart(s) to show
charts = {
    "Officer vs Camera by Borough": "dashboard/officer_vs_camera_borough.png",
    "Violations by Hour of Day":     "dashboard/violations_by_hour.png",
    "Share Over Time (%)":           "dashboard/share_over_time.png",
    "Heatmap Borough x Month":       "dashboard/heatmap_borough_month.png",
    "Top Violation Codes":           "dashboard/top_violation_codes.png",
    "Top Repeat Offenders":          "dashboard/top_repeat_offenders.png",
}
sel = st.sidebar.multiselect("Select visualizations", list(charts.keys()), default=list(charts.keys()))

# ─── MAIN PANEL ───────────────────────────────────────────────────────
for title in sel:
    path = charts[title]
    if os.path.exists(path):
        st.subheader(title)
        st.image(path, use_column_width=True)
    else:
        st.warning(f"Chart not found: `{path}`")

# ─── REPEAT OFFENDERS DATAFRAME ───────────────────────────────────────
st.subheader("🔢 Repeat Offenders Detail")
df_rep = load_repeat_offenders()
if not df_rep.empty:
    st.dataframe(df_rep)
    csv = df_rep.to_csv(index=False).encode('utf-8')
    st.download_button("Download CSV", csv, file_name="repeat_offenders.csv")
else:
    st.write("No repeat offenders data available.")

# ─── RAW SAMPLE ──────────────────────────────────────────────────────
st.subheader("🗃️ Sample Raw Data")
try:
    df_sample = pd.read_sql("SELECT * FROM cleaned_parking_violations LIMIT 100", engine)
    st.dataframe(df_sample)
except Exception as e:
    st.write("Unable to load sample raw data from DB.")
