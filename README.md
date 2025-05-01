# IA-626 Final Project: NYC Parking & Camera Violations Analysis Project

## Project Overview and Objective

 This project is an end-to-end analysis of New York City parking and camera violation data. It demonstrates a full ETL (Extract, Transform, Load) pipeline and interactive data exploration. The primary goal is to uncover patterns and insights in NYC's parking tickets and camera-issued violations, such as when and where violations are most common, which violations are issued most frequently, and who the repeat offenders are.
 To achieve this, we:
  - Extracted data from NYC OpenData via the Socrata API for two large datasets (parking violations and camera violations).
  - Transformed and cleaned the data using Python and SQL (MySQL), creating a structured database with staging tables, refined tables, and aggregated summary tables for analysis.
  - Loaded the data into a MySQL database using SQLAlchemy, automatically creating the schema and inserting millions of records.
  - Analyzed the data with SQL queries to produce cleaned datasets and key aggregated metrics (counts by violation type, time of day, etc.).
  - Visualized the results using Matplotlib and Seaborn, creating charts (bar charts, heatmaps, stack plots, histograms) to illustrate trends and findings.
  - Developed a Streamlit dashboard (app.py) to allow interactive exploration of the insights (e.g. filtering by violation type or time period, viewing charts dynamically).

 By combining automated data retrieval, database management, analysis, and a user-friendly dashboard, the project provides a comprehensive view of NYC parking enforcement activity and demonstrates best practices in data engineering and data analysis.



## Data Sources and Datasets

All data comes from the NYC OpenData platform. We use two complementary datasets made available by the NYC Department of Finance:
 ### 1. Parking Violations Issued – Fiscal Year 2024
 Dataset ID: pvqr-7yc4 (NYC OpenData portal)
 Description: This dataset contains all parking violation tickets issued in New York City between July 1, 2023 and June 30, 2024, corresponding to NYC Fiscal Year 2024​. Each row represents a single parking summons issued by authorities (e.g. traffic enforcement agents or police). Notably, this dataset is static – it reflects the tickets at the time of issuance and is not updated to show whether tickets were later paid or dismissed​. It’s essentially a snapshot of all tickets issued in that fiscal year. 

 ##### Key fields include: Summons Number (unique ticket ID), Issue Date (date the ticket was issued), Violation Code and Violation Description (identifying the offense type, e.g. expired meter, illegal parking), Vehicle Details (license plate ID, state of registration, vehicle body type, vehicle make), Issuer information (agency or precinct that issued the ticket), and Fine amount (the monetary penalty)​. There are 40+ columns in total capturing various details of the violation record. (For full field definitions, see the NYC OpenData portal or dataset documentation.) Link: NYC OpenData – Parking Violations Issued (FY2024)

- [Parking Violations FY2024](https://data.cityofnewyork.us/resource/pvqr-7yc4.json)

### 2. Open Parking and Camera Violations
 Dataset ID: nc67-uf89 (NYC OpenData portal)
 Description: This is a live, continually-updated dataset of all open parking and camera violations in NYC. It was initially populated with all violations recorded in the city’s database as of May 2016​. New violations are added on a weekly basis, and any updates to existing violations (e.g. payments made, hearings results, status changes) are applied daily​. In practice, this dataset contains every parking ticket and camera-issued violation from mid-2016 to present, along with the current status of each. Unlike the fiscal year issuance dataset above, this “Open” dataset includes fields that indicate whether a violation has been paid, dismissed, is still outstanding, or was written off (e.g. blank fields for financials indicate the ticket was dismissed or expired without payment​). 

 ##### Key fields include: similar identifiers and details as the FY2024 dataset (Summons Number, issue date, violation code/description, plate, vehicle, location, etc.) plus additional financial and status fields. For example, it has fields for payment amounts, payment dates, penalties and interest (for late payments), and indicators of the ticket’s status (open, paid, dismissed, etc.). These allow us to determine which tickets are still open/unpaid versus resolved. It also covers both regular parking violations and camera violations (like red-light camera tickets and bus lane or speed camera tickets) in one combined dataset.

 - [Open Parking & Camera Violations](https://data.cityofnewyork.us/resource/nc67-uf89.json)

 `How these datasets are used in our project`: We leverage the Fiscal Year 2024 issuance dataset as a fixed sample of violations to analyze patterns in a recent year. We then use the Open Violations dataset to enrich this sample with current status information. For instance, by matching tickets from FY2024 against the Open dataset (using the Summons Number), we can flag which of those tickets have been paid or are still outstanding. This gives a more complete picture of outcomes (e.g., what percentage of tickets get paid) beyond just issuance counts. The combination of these datasets enables analysis of both the issuance trends and the resolution status of violations.

## Data Extraction via Socrata API
 NYC OpenData provides a RESTful API (the Socrata Open Data API, or SODA) to query and retrieve datasets programmatically. We built a Python-based extraction tool that connects to this API to download the data instead of manually exporting CSV files. Key aspects of our data extraction methodology:
 - `Socrata API & Authentication`: We used the Socrata API endpoints for each dataset (identified by their 8-character IDs above) to fetch the data in JSON format. An app token was used in our requests to authenticate and comply with API usage policies (this helps avoid strict throttling). The Socrata API base URL for NYC OpenData is https://data.cityofnewyork.us/resource/ – for example, the FY2024 dataset endpoint is https://data.cityofnewyork.us/resource/pvqr-7yc4.json. We accessed these endpoints using Python (with libraries such as requests or Socrata’s own Python client).

 - `Pagination (Batch Retrieval)`: Each dataset contains millions of records, so we implemented pagination to retrieve data in manageable chunks. By default, the Socrata API returns a maximum of 1000 records per request​. We utilized the $limit and $offset query parameters to page through the data. For example, we requested 5,000 records at a time (the API allows setting a higher limit up to certain maximums) and incremented the offset in loops until all records were retrieved.

 Pseudocode:
 ```bash
 limit = 5000
 offset = 0
 all_records = []
 while True:
    query_url = f"https://data.cityofnewyork.us/resource/pvqr-7yc4.json?$limit={limit}&$offset={offset}"
    batch = requests.get(query_url, headers={"X-App-Token": APP_TOKEN}).json()
    if not batch:
        break  # no more records
    all_records.extend(batch)
    offset += limit

 ```
 This approach ensured we didn’t overwhelm the API or run into response size limits. We also included an $order parameter on a unique field (like Summons Number or issue date) when paging, to guarantee a consistent ordering of results across pages​. This prevents any potential overlap or skipping of records when the data is not inherently ordered.

 - `API Usage Considerations`: We handled network interrupts and rate limits by implementing retries and respecting recommended delays if needed. With an app token, the API allows higher throughput, but we still monitored for any HTTP status indicating we should slow down. In practice, the extraction for each dataset might take a few minutes to complete given the volume of data (tens of millions of records combined).
 - `Data Format`: The data was retrieved in JSON. We parsed the JSON into Python objects and immediately wrote the records to the database (as opposed to storing everything in memory). This streaming insertion (explained below) allowed us to handle the large dataset efficiently.

 By using the Socrata API, our ETL process remains up-to-date and reproducible – we can re-run the extraction at any time to get the latest data (for example, to fetch FY2025 data in the future or update the open violations).


## Database Schema and Design

We chose MySQL as the relational database to store and manage the data. Using a database allows us to run powerful SQL queries for cleaning and aggregating the data and also to serve the data to the dashboard efficiently. The schema is designed with three layers of tables: staging tables, cleaned tables, and aggregated tables.

### Staging Tables (Raw Data)

These tables mirror the structure of the source datasets and hold the data exactly as it was extracted, without any processing (except for minor type conversions).

- `parking_violations_raw`: Contains raw records from the Parking Violations Issued FY2024 dataset. All original fields (approximately 43 columns) are present, such as `summons_number`, `plate_id`, `issue_date`, `violation_code`, `violation_description`, and more.
- `open_violations_raw`: Stores raw records from the Open Parking and Camera Violations dataset. It has a similar schema to the previous table but includes additional financial and status fields like `payment_amount`, `payment_date`, and `outstanding_amount`.

Schema creation was done using SQLAlchemy (Python’s ORM). We defined appropriate data types (`DATE`, `DATETIME`, `INT`, `VARCHAR`, etc.) and issued `CREATE TABLE` statements to MySQL. Data was then bulk inserted using SQLAlchemy sessions.

### Cleaned / Refined Tables

Once the raw data was loaded, we performed transformations and integration steps to produce refined tables optimized for analysis.

#### Merging Datasets

We joined the FY2024 parking violations table with the open violations table on the `summons_number` to enrich the FY2024 records with current status information. This allowed us to label tickets as "Paid", "Dismissed", or "Open", and to flag unpaid tickets by checking for non-zero outstanding balances.

We created a new table:

- `parking_violations_fy2024_cleaned`: Combines relevant fields from both datasets. If a FY2024 record had no match in the open violations dataset, we assumed it was resolved or not open.

#### Data Cleaning

Several standardization and cleanup steps were performed:

- Trimmed whitespace and normalized text case (e.g., `plate_id`, `violation_county`).
- Converted the `violation_time` field (e.g., "0130P") to a proper time or hour-of-day integer.
- Parsed all `issue_date` values to MySQL `DATE` type.
- Enforced uniqueness constraints (e.g., primary key on `summons_number`) to avoid duplication.
- Filtered out records with missing or invalid data (e.g., blank `issue_date`, malformed time codes).

#### Field Selection

We reduced the column set from over 40 to a manageable number of key analytical fields, such as:

- `summons_number`, `issue_date`, `hour_of_day`, `violation_code`, `violation_description`, `plate_id`, `registration_state`, `violation_county`, `status`

Financial columns like `fine_amount`, `payment_amount` were retained for flagging ticket resolution status but not heavily analyzed in the main cleaned table.

### Aggregated Tables (Summary Insights)

To optimize dashboard responsiveness and facilitate exploratory analysis, we pre-computed several aggregates and stored them as dedicated tables. SQL `GROUP BY` queries were used to populate these summary tables from the cleaned data.

- **`agg_violations_by_type`**: Total number of violations by code and description.
- **`agg_violations_by_hour`**: Counts grouped by hour of the day (0–23).
- **`agg_violations_by_day`**: Counts grouped by day of the week (Monday–Sunday).
- **`agg_violations_by_month_type`**: Monthly violation counts, optionally grouped by type.
- **`agg_heatmap_day_hour`**: Matrix of violation counts by day-of-week and hour-of-day (for heatmaps).
- **`agg_repeat_offenders`**: Summarizes number of violations per unique vehicle (plate ID), including state and total count.

These aggregates greatly reduce dashboard latency, as queries against smaller, purpose-built tables are much faster than live aggregations on millions of rows.

All tables reside within a single MySQL database named:

Schema Overview:

- **`Staging`**: parking_violations_raw, open_violations_raw
- **`Cleaned`**: parking_violations_fy2024_cleaned
- **`Aggregates`**: agg_violations_by_type, agg_violations_by_hour, agg_violations_by_day, agg_repeat_offenders, agg_violations_by_month_type, etc.
(The exact table names and schema definitions can be found in the repository’s SQLAlchemy models or DDL scripts.)

## ETL Process Description

Our ETL process is implemented in Python and SQL and can be outlined in a series of steps:

### Extraction (E)

The Python ETL script connects to the Socrata API for each dataset and downloads the data in chunks. As described in the Data Extraction section, it iterates with increasing offsets to page through all records. After retrieving each batch of records from the API, the script immediately writes them to the database to avoid accumulating too much in memory. We used SQLAlchemy’s database session to add records in bulk. 

In practice, for each batch of ~5,000 records, we converted them into a list of Python dicts or ORM objects and used `session.bulk_insert_mappings()` (for raw tables) to quickly load them into MySQL. This approach is efficient for large inserts. The extraction step handles both datasets sequentially: first load `parking_violations_raw`, then `open_violations_raw`. By the end of this stage, the MySQL staging tables contain all the raw data.

### Transformation (T)

Once data is in the database, we perform data transformation using SQL queries (executed either via SQLAlchemy or a db client):

#### Data Cleaning

We run SQL `UPDATE` or `INSERT-SELECT` queries to populate the cleaned table. This involves joining the two staging tables to combine columns, as well as applying functions to clean values. For example:

##### Joining

We execute a query to select all columns from `parking_violations_raw` along with a payment status from `open_violations_raw` (joined on summons number). This result is inserted into `parking_violations_fy2024_cleaned`. We use a `LEFT JOIN` so that all FY2024 tickets appear; if a ticket has a match in `open_violations_raw`, we pull in its `payment_status` (or derive a status like “Open” vs “Paid”); otherwise, we mark it as closed.

##### Type Conversion

We cast date strings to date types using MySQL’s `STR_TO_DATE` function (e.g., `STR_TO_DATE(issue_date, '%m/%d/%Y')`). We also parse the time. The violation time in the source is a string with a format where the last character is A/P for AM/PM. We wrote a small SQL function (or did it in Python prior to insertion) to convert that into a 24-hour time or at least extract the hour (for aggregation purposes). The cleaned table might include an integer column for `issue_hour` (0–23).

##### Cleaning Values

We removed any whitespace/padding from text fields using `TRIM()`, and uppercased certain fields for consistency (e.g., state codes are stored as uppercase). We also handled `NULLs`: any empty strings were set to SQL `NULL` for easier handling in aggregates (e.g., if a vehicle make was missing, it’s `NULL` rather than an empty string).

##### Filtering

If any records in staging were clearly erroneous (such as a date out of range or a missing summons number), we excluded them from the cleaned table. Overall, the data was fairly clean, but we applied sanity checks.

#### Aggregations

After obtaining the cleaned table, we execute a series of `SELECT ... GROUP BY ...` queries to create the aggregate tables:

##### Violations by Type

```sql
INSERT INTO agg_violations_by_type
SELECT violation_code, violation_description, COUNT(*) 
FROM parking_violations_fy2024_cleaned
GROUP BY violation_code, violation_description;
```
##### Violations by Hour
```sql
INSERT INTO agg_violations_by_hour
SELECT issue_hour, COUNT(*) 
FROM parking_violations_fy2024_cleaned 
GROUP BY issue_hour;
```

##### Violations by Day of Week
Here we used MySQL’s DAYOFWEEK() or WEEKDAY() function on the date to get the day index.

##### Violations by Month and Type
We added a month column via MONTH(issue_date) or formatted Year-Month, then grouped by month and perhaps violation category. For a stackplot, we focused on a few major violation categories: we could generate a table that has columns for each category and rows for each month, or simply prepare data on the fly. In our case, we prepared data via SQL for ease, e.g.,
``` sql
SELECT MONTH(issue_date) as month, violation_category, COUNT(*) 
FROM parking_violations_fy2024_cleaned
GROUP BY month, violation_category;
```
##### Repeat Offenders
```sql
INSERT INTO agg_repeat_offenders
SELECT plate_id, registration_state, COUNT(*) as violations_count 
FROM parking_violations_fy2024_cleaned
GROUP BY plate_id, registration_state;
```

We could further filter this table in queries (e.g., WHERE violations_count > 1 for repeat offenders, or sort to get top offenders).

We ensured to index certain fields in the cleaned table (like summons_number, violation_code, issue_date, plate_id) to speed up the JOIN and GROUP BY queries. This made the transformation step run faster on the large dataset.

The transformation step is where the heavy lifting of data wrangling happens. By using MySQL’s capabilities, we leverage set-based operations, which are typically faster than processing millions of records in pure Python.

###  Loading (L)
In the context of our pipeline, “Loading” primarily referred to inserting data into the final database tables (which we actually did alongside extraction for staging data, and after transformation for aggregate data). By the end of the ETL process, all tables (staging, cleaned, aggregates) are populated in MySQL.

We then verify row counts and basic statistics (e.g., the sum of counts in the aggregate tables should equal the total rows in cleaned for sanity). The database is now ready to be queried by the dashboard or any other analysis tools.

This entire ETL process can be run in one go by executing the provided Python script (etl_pipeline.py) or Jupyter Notebook. Logging is included to track progress (e.g., printing how many records have been fetched/inserted per batch). On a capable machine, the pipeline might take on the order of tens of minutes to run due to the volume of data and index creation, but it is designed to be robust and repeatable.

## Visualizations and Insights

We created a variety of visualizations using Matplotlib and Seaborn to illustrate the insights derived from the data. Below is a list of the main charts and what they show:

### Bar Charts

We used bar charts to compare categorical frequencies. One prominent bar chart is the "Top 10 Violation Types," showing the ten most common parking violations in FY2024 by volume. Each bar represents a violation code (with a label for its description) and its height is the number of tickets issued for that offense. This makes it immediately clear which violations are most frequent (for example, one might observe that violations like "No Parking Street Cleaning" or "Expired Meter" are leading offenses).

Another bar chart shows the number of violations by borough (Manhattan, Brooklyn, etc.), highlighting which areas see the most tickets. This can reflect factors like traffic density and enforcement patterns in different parts of the city.
![image1](Final_Project_IA626/dashboard/top_violation_codes.png)
![image4](Final_Project_IA626/dashboard/top_repeat_offenders.png)

### Heatmap

We produced a heatmap to visualize the concentration of violations by time of week. On one axis, we have the day of the week (Monday through Sunday) and on the other axis, the hour of the day (0–23h). Each cell’s color intensity indicates the number of tickets issued in that day-hour slot (darker means more tickets). 

This heatmap reveals temporal patterns: for instance, we might see that weekday mornings around 8-10 AM have a high density of tickets (likely due to street cleaning regulations and rush-hour no-standing rules), whereas the early hours of the morning on weekends have very few tickets. Such a visualization helps identify when enforcement is busiest and can correlate to known parking rules schedules. The heatmap was created using Seaborn’s heatmap function on a pivot table of counts (from the aggregate table of day vs hour counts).
![heatmap](Final_Project_IA626/dashboard/heatmap_borough_month.png)


### Stack Plot (Stacked Area Chart)

To observe trends over time and compare categories, we generated a stacked area chart of monthly violations, broken down by major violation categories. For example, we grouped violations into a few broad categories (or chose a few top violation codes to track individually) and plotted the number of tickets each month for each category, stacked on top of each other. The x-axis is time (July 2023 through June 2024) and the y-axis is the cumulative count of tickets. 

Each colored band represents a category’s contribution. This visualization shows overall seasonality (total area) and also if certain types of violations spike in certain months. One might notice, for example, a dip in tickets in the winter months (perhaps due to holidays or snow days) or an uptick in spring. The stackplot also shows if one category grows as a share of total violations over time. We used Matplotlib’s stackplot for this, feeding in data from an aggregate grouped by month and category.

![image3](Final_Project_IA626/dashboard/share_over_time.png)

### Hourly Distribution Histogram

We created a histogram focusing on the distribution of tickets by hour of the day. This is similar data to one axis of the heatmap but aggregated over all days. The histogram (or a line plot) shows how ticket frequency rises and falls during the day. Typically, we expect few tickets in the early morning hours (midnight to 6 AM), then a sharp increase during the morning (peaking perhaps around 9 AM), some plateau or secondary peak in the afternoon (for meter violations), and then a drop in the late evening. 
![image5](Final_Project_IA626/dashboard/violations_by_hour.png)
This chart helps validate and quantify those intuitions. It was generated by grouping data by hour and plotting the counts as a bar for each hour (0–23).




### Top Violations (Detailed)

In addition to the bar chart of top 10 violations, we also compiled tables or additional charts to detail these top offenses. For example, we listed the violation codes along with their descriptions and total counts, and computed their percentage of all tickets. This shows, for instance, the top 3 violations might account for a significant fraction of all tickets.

In the dashboard, we allow users to see the breakdown or filter by a particular violation code to see its pattern over time or by location. While this is not a separate chart type, it’s an important part of the analysis to communicate what the violations actually are (since codes like 21 or 14 need explanation, e.g., code 21 might correspond to "Street Cleaning: No Parking").

### Repeat Offenders Analysis

To understand how many tickets are being accumulated by the same vehicles, we looked at the distribution of tickets per unique vehicle (license plate). We visualized this in a couple of ways. One was a bar chart of the top 5-10 “repeat offender” vehicles – essentially, the license plates (anonymized in the report for privacy) that received the most tickets in FY2024, and the count of tickets for each. It’s not uncommon to find certain vehicles with dozens of tickets, indicating habitual offenses or possibly commercial vehicles that incur tickets as a cost of doing business.

Another view was a histogram of violations count per vehicle: for example, X number of vehicles got 1 ticket, Y vehicles got 2 tickets, down to a few vehicles that got 50+ tickets. This distribution is usually heavily skewed toward 1 ticket per vehicle (most people only get one ticket), with a long tail of repeat offenders. 

Such analysis was made possible by the aggregated `repeat_offenders` table we created. It provides insight into enforcement impact – e.g., are many tickets coming from the same violators or spread widely among the population.
![image2](Final_Project_IA626/dashboard/officer_vs_camera_borough.png)

### Dashboard Integration

All visualizations are integrated into the Streamlit dashboard for interactive exploration. Users can hover to see exact values, filter by categories, and so on. The combination of these plots paints a detailed picture of NYC parking violations: when they happen, what they are for, and who they affect the most.

## SQL Transformations and Analysis Details

Our analysis relied heavily on SQL for transforming the raw data into meaningful information. Below is a summary of the key SQL-based transformations and queries:

### Joining Datasets for Status

We wrote a SQL query to join the FY2024 violations with the open violations on the summons number. This looked roughly like:

```sql
INSERT INTO parking_violations_fy2024_cleaned 
SELECT p.*, 
       CASE 
          WHEN o.summons_number IS NULL THEN 'Resolved' 
          ELSE 
            (CASE 
               WHEN o.payment_amount > 0 THEN 'Paid' 
               WHEN o.fine_amount IS NULL THEN 'Dismissed' 
               ELSE 'Open' 
             END) 
       END as status,
       o.payment_date, o.payment_amount, o.outstanding_amount
FROM parking_violations_raw p
LEFT JOIN open_violations_raw o 
  ON p.summons_number = o.summons_number;
```
This allowed us to assign a status to each ticket. We used logic such that if a record from the FY dataset had a matching open record, we check if it has a payment recorded (then mark “Paid”), or if the financial fields are blank, which can indicate dismissal or write-off (“Dismissed”), otherwise mark it as “Open” (unpaid). If there was no matching open record, we assumed it’s resolved outside the open dataset (though as noted, in practice, all should match since open data includes paid ones too). This join greatly enriched our data for later analysis of outcomes.

### Deriving Time Components

Using SQL functions, we added extra columns for analysis convenience:

- **issue_datetime**: combining date and time into one DATETIME field (if not already provided as such).
- **issue_hour**: using `HOUR(issue_datetime)` or parsing the text time. If the time was given as a separate field (e.g., "01:30 PM"), we converted it. For example, one approach: `CASE WHEN RIGHT(raw_time,1)='P' AND LEFT(raw_time,2)!='12' THEN LEFT(raw_time,2)+12 ELSE LEFT(raw_time,2) END` to get hour in 24h (accounting for AM/PM), and then cast to int. We also handled midnight (12 AM) carefully in that logic. This gave us an integer 0–23.
- **issue_dayofweek**: using `DAYOFWEEK(issue_date)` which returns 1=Sunday, 7=Saturday in MySQL. We converted that to a value or string Monday–Sunday for readability. Alternatively, `WEEKDAY(issue_date)` returns 0=Monday, etc.
- **issue_month**: using `MONTH(issue_date)` and `YEAR(issue_date)` to identify the month and year.

These derived fields were either added to the cleaned table or used on the fly in aggregate queries.

### Cleaning Text Fields

Some fields like `violation_description` or `vehicle_make` might contain inconsistent casing or abbreviations. We ensured `violation_description` is properly capitalized or in title case for presentation. We standardized state codes (the raw data uses postal codes like NY, NJ, etc., which were already consistent). We also trimmed any extraneous whitespace (e.g., plate IDs sometimes have leading zeros or spaces – we kept leading zeros if they are part of the plate, but trimmed spaces).

### Handling Nulls and Defaults

In the open dataset, some numeric fields like `fine_amount`, `penalty`, and `interest` could be blank for older tickets that were written off. When we joined, those came as NULL. We left them as NULL in the cleaned table, and in the status logic above, we interpreted NULL fine as an indicator of dismissal (this is per the dataset documentation: violations written off have blank financials). For aggregation, when counting tickets, these NULLs in financial fields don’t matter because we count rows. But for any sum of fines or similar (if we had done such analysis), we’d treat NULL as 0 or exclude those cases accordingly.

### Aggregations

We wrote multiple SQL queries to compute aggregates, as described in the Visualizations section. Some examples:

- **Top violation types**:
```sql
    SELECT violation_code, violation_description, COUNT(*) AS cnt 
    FROM parking_violations_fy2024_cleaned 
    GROUP BY violation_code, violation_description 
    ORDER BY cnt DESC LIMIT 10;
```

- **Tickets by day/hour**:
```sql

    SELECT issue_dayofweek, issue_hour, COUNT(*) 
    FROM parking_violations_fy2024_cleaned 
    GROUP BY issue_dayofweek, issue_hour; 
```

The result of this was pivoted in Python to make the heatmap (or we could pivot in SQL using `CASE` when grouping by day to get columns, but it was straightforward to do in pandas).

- **Monthly trend**:
```sql
    SELECT MONTH(issue_date) as month, YEAR(issue_date) as year, COUNT(*) 
    FROM parking_violations_fy2024_cleaned 
    GROUP BY YEAR(issue_date), MONTH(issue_date) 
    ORDER BY year, month;
```
Since FY2024 spans two calendar years, we accounted for the year in ordering. We extended this to group also by violation category by adding that in select and group by.

- **Borough breakdown**:
```sql
    SELECT violation_county, COUNT(*) 
    FROM parking_violations_fy2024_cleaned 
    GROUP BY violation_county;
```
This yields counts for each borough (with codes like BX, BK, MN, QN, SI for Bronx, Brooklyn, Manhattan, Queens, Staten Island).

- **Repeat offender distribution**:
```sql
    SELECT violations_count, COUNT(*) 
    FROM agg_repeat_offenders 
    GROUP BY violations_count;
```
If `agg_repeat_offenders` has one row per plate with their count, this query tells how many plates had 1 ticket, 2 tickets, etc. Alternatively, we could do directly on cleaned data:
```sql
    SELECT COUNT(*) AS vehicle_count, violation_count = X;
```
But it’s easier after we have that table.

### Using SQL vs Python

We leaned on SQL for these computations as it’s set-based and efficient. In some cases, we cross-verified results with Python (pandas) to ensure correctness. For example, after computing top 10 violations in SQL, we might do a quick pandas `value_counts()` on the DataFrame to see if it matches. This helped validate that our transformations (like join and cleaning) did not accidentally drop or duplicate data.

### Performance Optimizations

We added indexes on key fields (like `summons_number` on both raw tables before joining, and on `plate_id` for counting per vehicle). We also made use of temporary tables for intermediate steps. For instance, instead of one huge complex SQL for the cleaned table, we could break it down: first create a temp table of FY2024 with status, then add derived columns. However, MySQL was able to handle the transformations in-place given the hardware we used, so a single pass was fine. We explicitly committed after large insertions to avoid open transactions on millions of rows.

In summary, SQL transformations allowed us to clean and summarize the data in a reproducible way. The resulting tables feed directly into the visualization code, and they also make it easy to answer specific queries (like "How many tickets were issued on weekends?" or "Which car make has the most tickets?") with simple SQL against our database.


## How to Run This Project

To run this project on your local machine (or server), follow these steps. Ensure you have the necessary software and meet the prerequisites.

###  Prerequisites

- **Python 3.9+** – The ETL and dashboard code is written in Python. You can download Python from [python.org](https://www.python.org) if not already installed.
- **MySQL 8+** – A MySQL database server is required to load and store the data. You can use a local MySQL instance (e.g., via installing MySQL Community Server or using Docker) or a remote MySQL database. Make sure you have the credentials (host, port, username, password) and permission to create a new database.
- **Socrata API App Token** – (Optional but recommended) Create a free account on Socrata and obtain an API application token. This token will be used to authenticate API requests to NYC OpenData, which can increase the rate limits. The app token is a string (e.g., `XAppToken=YOUR_TOKEN_HERE`). If you choose not to use a token, the code will still work but might be subject to stricter throttling.

###  Installation and Setup

- **Clone the repository**: Download or clone the project repository to your local machine. The repository should include the Python scripts (`etl_pipeline.py`, `app.py`, etc.), a `requirements.txt` file for Python dependencies, and possibly SQL files or Jupyter notebooks.

```bash
git clone https://github.com/yourusername/nyc-parking-analysis.git
cd nyc-parking-analysis
```

- **Python Dependencies** : Install the required Python libraries. They are listed in `requirements.txt`. Key dependencies include:

- **pandas**: Used for data manipulation and processing. It’s essential for handling and cleaning datasets in various stages of the ETL pipeline.
- **requests** or **sodapy**: These libraries are used to make API calls. `requests` is a general-purpose HTTP library, and `sodapy` is specifically designed for interacting with Socrata Open Data APIs.
- **SQLAlchemy**: This is an ORM (Object Relational Mapper) for Python, providing a toolkit for database connection and querying. It abstracts away raw SQL queries and simplifies the interaction with databases like MySQL.
- **PyMySQL** or **mysqlclient**: These are MySQL database drivers that work with SQLAlchemy to enable Python to connect to a MySQL database. Choose one based on compatibility or preference.
- **matplotlib** and **seaborn**: These are powerful libraries for data visualization. `matplotlib` provides a wide range of static, animated, and interactive plots, while `seaborn` offers a higher-level interface for drawing attractive and informative statistical graphics.
- **streamlit**: Used for building interactive web apps directly from Python scripts. In this project, it’s used to create the dashboard to visualize parking data interactively.

Once the repository is cloned and you've navigated into the project folder, install all the dependencies using:

``` bash
pip install -r requirements.txt
```

- **Database Setup**: Ensure your MySQL server is running. Then do the following:
 - Create a database for the project (if the code doesn’t create it automatically). For example, in a MySQL client or command line:
 ``` sql
 CREATE DATABASE nyc_parking_analysis;
 ```
 - Update the database connection settings in the project configuration. The connection details (host, user, password, database name) might be stored in a config file or as variables in etl_pipeline.py and app.py. For example, there might be a config.ini or you may need to edit DATABASE_URI in the code (which could look like mysql+pymysql://username:password@localhost:3306/nyc_parking_analysis). Enter your MySQL credentials and database name accordingly.
 -  If using an .env file for sensitive info, create a .env file in the project root and add the needed secrets (like MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, SOCRATA_APP_TOKEN, etc.). Make sure the code loads these (it might use Python-dotenv).

- **Socrata API Token**: If you have an App Token, add it to the config. For instance, set an environment variable SOCRATA_APP_TOKEN or put it in the script. The code will check for this token and include it in the API request header for efficiency.

### Running the ETL Pipeline

Execute the ETL script to fetch data from the API and populate the database. This may take some time due to the data size. Watch the console logs for progress updates. The script will:

- **Connect to MySQL** and create the necessary tables (via SQLAlchemy) if they don’t already exist.
- **Fetch the Parking Violations FY2024 data** in batches and insert it into the `parking_violations_raw` table.
- **Fetch the Open Parking & Camera Violations data** in batches and insert it into the `open_violations_raw` table.
- **Perform SQL transformation steps**: Joining tables, cleaning data, and creating aggregate tables.
- **Commit all changes** to the database.

### Running the Streamlit Dashboard

Once the data is loaded and processed, launch the Streamlit app to interact with the analysis. The app will:

- **Query the MySQL database** to retrieve the aggregated data for plotting.
- **Display interactive charts** and allow filtering by various parameters (such as borough, violation type, etc.).
- Ensure the **app can connect to the database**. If the app cannot connect, check that MySQL is running, and the credentials in the app's configuration (e.g., `config.ini`, `.env`, or `app.py`) are correct. If necessary, supply the database credentials directly to Streamlit.

### Viewing Results

With the app running, you can explore all the findings through the dashboard. Use interactive charts to filter by borough, violation type, or see statistics for specific license plates.

You may also view **static charts** by running the plotting script, if one is provided (e.g., in a Jupyter notebook or separate Python script). However, the Streamlit app is the preferred method for presenting the results in an interactive format.

### Cleanup and Updates

After use, if you want to free up space, you can drop the database or specific tables. To do so, you can connect to MySQL and execute the following commands:

 ```sql
 DROP DATABASE nyc_parking_analysis;
 ```
To update data, adjust parameters in the ETL script (for example, change the dataset ID to a new fiscal year, or fetch additional data from open violations) and re-run it.

If deploying to the cloud or sharing the dashboard publicly, additional steps such as configuring cloud databases or deploying Streamlit to a cloud service (e.g., Heroku, AWS, GCP, or Azure) may be required.

### Future Work
This project can be extended in several ways to derive deeper insights or broaden its scope:

 - **Expand to Other Years**: Incorporate data from multiple years to examine trends over time. Analyzing the impact of events, such as the COVID-19 pandemic, could provide valuable insights on parking enforcement changes during special circumstances.

 - **Geospatial Analysis**: Perform analysis at a more granular level such as by precinct or coordinates. This could enable visualizations such as heatmaps or interactive maps showing ticket hotspots across the city.

 - **Fine Revenue Analysis**: Calculate total revenue from fines, average fine amounts, and payment rates. This could be useful from a city revenue perspective, offering insights into ticket payment trends.

 - **Machine Learning Models**: Use models to predict certain outcomes such as the likelihood of a ticket being paid vs dismissed based on features (location, violation type, etc.), or cluster violation patterns. You could also explore using time-series forecasting to predict future ticket issuance volumes.

 - **Real-time Dashboard Enhancements**: Add more interactive features to the Streamlit dashboard, such as date range filters, search for a specific license plate, or linking related charts. For example, clicking on a bar in the violation type chart could filter the heatmap to only that violation type.

 - **Optimization and Scaling**: Improve performance for large datasets. As the dataset grows, performance tuning may become necessary. Consider integrating big data tools (e.g., Spark, Hadoop) if analyzing decades of data. For now, MySQL can handle it, but millions of records may require more robust data processing.

 - **Incorporate Other Violation Types**: Expand the analysis to include other types of violations available in the NYC OpenData platform, such as traffic moving violations or meter violations logs. This will provide a more comprehensive view of traffic enforcement in NYC. For example, comparing parking violations with moving violations (e.g., speeding tickets) might reveal interesting contrasts or correlations in enforcement patterns.

By pursuing some of these future enhancements, one could turn this project into a more complete NYC Traffic Violations Analytics Platform, valuable for urban planners, law enforcement policy, or just to satisfy public curiosity on parking habits in the city.

### Acknowledgments
 - NYC OpenData: We thank the NYC OpenData program and the Department of Finance for publishing the parking violations datasets. This public data made the project possible. The use of the data is in accordance with NYC OpenData terms catalog.data.gov.

 - Socrata: We are grateful for Socrata’s API and their documentation, which helped us efficiently retrieve the data.

 - Open-Source Libraries: This project leverages many open-source Python libraries, including SQLAlchemy, pandas, Streamlit, and matplotlib. We acknowledge the developers and maintainers of these libraries.

 - Community Resources: The project drew inspiration and techniques from community examples, including Kaggle datasets and open-source notebooks. These resources helped validate our approach to data cleaning, analysis, and visualization for NYC parking tickets.
