import os
import requests
import json
from datetime import datetime

import matplotlib.pyplot as plt
import seaborn as sns

from sqlalchemy import (
    create_engine, text, MetaData, Table, Column, String, Date, insert
)
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError


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
ENGINE = create_engine(db_url, echo=False)

try:
    with ENGINE.connect():
        print('[DB] Connection successful')
        DB_AVAILABLE = True
except OperationalError as e:
    print(f"[ERROR] DB connection failed: {e}")
    print("[WARN] Continuing without database operations")
    DB_AVAILABLE = False

os.makedirs('dashboard', exist_ok=True)

# --- Schema Definition ---
meta = MetaData()

parking = Table('parking_violations', meta,
    Column('summons_number',  String(50)),
    Column('plate_id',         String(20)),
    Column('issue_date',       Date),
    Column('violation_time',   String(10)),
    Column('violation_code',   String(10)),
    Column('violation_county', String(10)),
)

camera = Table('camera_violations', meta,
    Column('summons_number', String(50)),
    Column('plate',          String(50)),
    Column('issue_date',     Date),
    Column('state',          String(10)),
)

if DB_AVAILABLE:
    meta.drop_all(ENGINE)
    meta.create_all(ENGINE)
else:
    print("[WARN] Skipping staging table creation due to no DB connection")

# --- ETL Function ---
def extract_and_load(table, dataset_id, page_size=500000, max_offset=1000000):
    print(f"[EXTRACT] Fetching {dataset_id}…")
    offset = 0
    all_records = []
    while offset <= max_offset:
        url = (
            f"https://data.cityofnewyork.us/resource/{dataset_id}.json"
            f"?$limit={page_size}&$offset={offset}"
        )
        batch = requests.get(url).json()
        if not batch:
            break
        print(f"  - fetched {len(batch)} rows @ offset={offset}")
        all_records.extend(batch)
        offset += page_size

    print(f"[LOAD] Preparing {len(all_records)} rows for `{table.name}`")
    if not DB_AVAILABLE:
        print("[SKIP] DB unavailable; skipping load")
        return

    valid_cols = {c.name for c in table.columns}
    with ENGINE.begin() as conn:
        conn.execute(text(f"DELETE FROM `{table.name}`"))
        buffer = []
        for rec in all_records:
            flat = {
                k: (json.dumps(v) if isinstance(v, (dict, list)) else v)
                for k, v in rec.items()
            }
            ds = flat.get('issue_date')
            if ds:
                try:
                    flat['issue_date'] = datetime.fromisoformat(ds).date()
                except:
                    flat['issue_date'] = None

            if table.name == 'camera_violations':
                flat['state'] = flat.get('state', 'Unknown')

            row = {col: flat.get(col) for col in valid_cols}
            buffer.append(row)
            if len(buffer) >= 500:
                conn.execute(insert(table), buffer)
                buffer.clear()
        if buffer:
            conn.execute(insert(table), buffer)
    print(f"[LOAD] `{table.name}` loaded")


if __name__ == '__main__':
    extract_and_load(parking, 'pvqr-7yc4')
    extract_and_load(camera, 'nc67-uf89')
    if DB_AVAILABLE:
        with ENGINE.begin() as conn:
            for tbl in [
                'cleaned_parking_violations',
                'cleaned_camera_violations',
                'fact_monthly_violations',
                'agg_top_violation_codes',
                'agg_repeat_offenders'
            ]:
                conn.execute(text(f"DROP TABLE IF EXISTS `{tbl}`"))

            # cleaned parking
            conn.execute(text("""
                CREATE TABLE cleaned_parking_violations AS
                SELECT
                  summons_number,
                  plate_id,
                  issue_date,
                  violation_code,
                  violation_county,
                  'officer' AS source,
                  DATE_FORMAT(issue_date, '%Y-%m-01') AS month
                FROM parking_violations
                WHERE issue_date IS NOT NULL
            """))

            conn.execute(text("""
                CREATE TABLE cleaned_camera_violations AS
                SELECT
                  summons_number,
                  plate       AS plate_id,
                  issue_date,
                  NULL        AS violation_code,
                  state       AS violation_county,
                  'camera'    AS source,
                  DATE_FORMAT(issue_date, '%Y-%m-01') AS month
                FROM camera_violations
                WHERE issue_date IS NOT NULL
            """))

            conn.execute(text("""
                CREATE TABLE fact_monthly_violations AS
                SELECT
                  month,
                  violation_county AS borough,
                  source,
                  COUNT(*)         AS violation_count
                FROM (
                  SELECT month, violation_county, source
                    FROM cleaned_parking_violations
                  UNION ALL
                  SELECT month, violation_county, source
                    FROM cleaned_camera_violations
                ) AS u
                GROUP BY month, violation_county, source
            """))

            conn.execute(text("""
                CREATE TABLE agg_top_violation_codes AS
                SELECT violation_code, COUNT(*) AS code_count
                FROM cleaned_parking_violations
                WHERE violation_code <> ''
                GROUP BY violation_code
                ORDER BY code_count DESC
                LIMIT 10
            """))

            conn.execute(text("""
                CREATE TABLE agg_repeat_offenders AS
                SELECT plate_id, COUNT(*) AS violation_count
                FROM cleaned_parking_violations
                GROUP BY plate_id
                HAVING violation_count >= 5
            """))

        print("Transforms complete")
    else:
        print("[WARN] Skipping transforms due to no DB connection")

    if DB_AVAILABLE:
        off, cam = {}, {}
        with ENGINE.connect() as conn:
            for r in conn.execute(text(
                "SELECT COALESCE(violation_county,'Unknown') AS b, COUNT(*) AS cnt "
                "FROM parking_violations GROUP BY b"
            )):
                off[r._mapping['b']] = r._mapping['cnt']
            for r in conn.execute(text(
                "SELECT COALESCE(state,'Unknown') AS b, COUNT(*) AS cnt "
                "FROM camera_violations GROUP BY b"
            )):
                cam[r._mapping['b']] = r._mapping['cnt']

        boroughs = sorted(set(off) | set(cam))
        x = range(len(boroughs))
        plt.figure(figsize=(10,6))
        plt.bar([i-0.2 for i in x], [off.get(b,0) for b in boroughs], width=0.4, label='Officer')
        plt.bar([i+0.2 for i in x], [cam.get(b,0) for b in boroughs], width=0.4, label='Camera', alpha=0.7)
        plt.xticks(x, boroughs, rotation=45, ha='right')
        plt.ylabel('Count')
        plt.title('Officer vs Camera Violations by Borough')
        plt.legend()
        plt.tight_layout()
        plt.savefig('dashboard/officer_vs_camera_borough.png')
        plt.close()

        hr_counts = {h:0 for h in range(24)}
        with ENGINE.connect() as conn:
            for r in conn.execute(text(
                "SELECT (CAST(violation_time AS UNSIGNED) DIV 100) AS hr, COUNT(*) AS cnt "
                "FROM parking_violations "
                "WHERE violation_time REGEXP '^[0-9]+' "
                "GROUP BY hr"
            )):
                h = r._mapping['hr']
                if h is not None and 0 <= h < 24:
                    hr_counts[h] = r._mapping['cnt']

        plt.figure(figsize=(12,5))
        plt.bar(list(hr_counts), list(hr_counts.values()))
        plt.xticks(list(hr_counts.keys()))
        plt.xlabel('Hour of Day')
        plt.ylabel('Count')
        plt.title('Parking Violations by Hour of Day')
        plt.tight_layout()
        plt.savefig('dashboard/violations_by_hour.png')
        plt.close()

        data = {}
        with ENGINE.connect() as conn:
            for r in conn.execute(text(
                "SELECT month, source, violation_count FROM fact_monthly_violations"
            )):
                m, s, c = r._mapping['month'], r._mapping['source'], r._mapping['violation_count']
                data.setdefault(m, {})[s] = c

        months = sorted(data)
        o = [data[m].get('officer',0) for m in months]
        c = [data[m].get('camera', 0) for m in months]
        tot = [oi + ci for oi, ci in zip(o, c)]
        pct_o = [oi/t*100 if t else 0 for oi, t in zip(o, tot)]
        pct_c = [ci/t*100 if t else 0 for ci, t in zip(c, tot)]

        plt.figure(figsize=(10,6))
        plt.stackplot(months, pct_o, pct_c, labels=['Officer','Camera'], alpha=0.7)
        plt.legend(loc='upper left')
        plt.title('Officer vs Camera Share Over Time (%)')
        plt.tight_layout()
        plt.savefig('dashboard/share_over_time.png')
        plt.close()


        pivot = {}
        with ENGINE.connect() as conn:
            for r in conn.execute(text(
                "SELECT borough, month, violation_count FROM fact_monthly_violations"
            )):
                b, m, c = r._mapping['borough'], r._mapping['month'], r._mapping['violation_count']
                pivot.setdefault(b or 'Unknown', {})[m] = c

        brds = sorted(pivot)
        mths = sorted({m for d in pivot.values() for m in d})
        mat  = [[pivot[b].get(m,0) for m in mths] for b in brds]

        plt.figure(figsize=(12,8))
        sns.heatmap(mat, xticklabels=mths, yticklabels=brds, cmap='YlGnBu')
        plt.title('Heatmap: Violations by Borough & Month')
        plt.tight_layout()
        plt.savefig('dashboard/heatmap_borough_month.png')
        plt.close()

        codes = []
        reps  = []
        with ENGINE.connect() as conn:
            codes = list(conn.execute(text(
                "SELECT violation_code, code_count FROM agg_top_violation_codes"
            )))
            reps  = list(conn.execute(text(
                "SELECT plate_id, violation_count FROM agg_repeat_offenders"
            )))

        if codes:
            vc, ct = zip(*[(r._mapping['violation_code'], r._mapping['code_count']) for r in codes])
            plt.figure(figsize=(8,5))
            plt.barh(vc, ct)
            plt.title('Top 10 Violation Codes')
            plt.tight_layout()
            plt.savefig('dashboard/top_violation_codes.png')
            plt.close()

        if reps:
            top10 = sorted(
                [(r._mapping['plate_id'], r._mapping['violation_count']) for r in reps],
                key=lambda x: x[1], reverse=True
            )[:10]
            plts, cnts = zip(*top10)
            plt.figure(figsize=(10,5))
            plt.bar(plts, cnts)
            plt.xticks(rotation=45, ha='right')
            plt.title('Top 10 Repeat Offenders (5+ Violations)')
            plt.tight_layout()
            plt.savefig('dashboard/top_repeat_offenders.png')
            plt.close()

        print("All visualizations saved into `dashboard/`")
    else:
        print("[WARN] Skipping visualizations: no DB connection")

    print("Pipeline complete!")




