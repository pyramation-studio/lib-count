# NPM Download Analytics Queries

This document contains SQL queries for analyzing NPM download statistics from the `npm_count` schema.

## Schema Overview

The database uses the following key tables:

- `npm_count.npm_package` - Package metadata (package_name, creation_date, last_publish_date, is_active)
- `npm_count.daily_downloads` - Daily download counts (package_name, date, download_count)
- `npm_count.category` - Package categories
- `npm_count.package_category` - Junction table linking packages to categories

---

## Total Downloads

### Current Total Downloads (All Time)

```sql
SELECT SUM(download_count) AS total_downloads
FROM npm_count.daily_downloads;
```

### Total Downloads by Category

```sql
SELECT 
    c.name AS category,
    SUM(dd.download_count) AS total_downloads
FROM npm_count.daily_downloads dd
JOIN npm_count.package_category pc ON dd.package_name = pc.package_id
JOIN npm_count.category c ON pc.category_id = c.id
GROUP BY c.name
ORDER BY total_downloads DESC;
```

### Total Downloads by Package (Top 50)

```sql
SELECT 
    package_name,
    SUM(download_count) AS total_downloads
FROM npm_count.daily_downloads
GROUP BY package_name
ORDER BY total_downloads DESC
LIMIT 50;
```

---

## Historical Comparisons

### Total Downloads as of a Specific Date

This query calculates the cumulative total downloads up to a specific point in time.

```sql
-- Total downloads as of 18 months ago
SELECT SUM(download_count) AS total_downloads_18_months_ago
FROM npm_count.daily_downloads
WHERE date <= CURRENT_DATE - INTERVAL '18 months';
```

### Compare Current Total vs 18 Months Ago

```sql
WITH current_total AS (
    SELECT SUM(download_count) AS total
    FROM npm_count.daily_downloads
),
historical_total AS (
    SELECT SUM(download_count) AS total
    FROM npm_count.daily_downloads
    WHERE date <= CURRENT_DATE - INTERVAL '18 months'
)
SELECT 
    h.total AS downloads_18_months_ago,
    c.total AS downloads_today,
    c.total - h.total AS growth_absolute,
    ROUND(((c.total - h.total)::numeric / NULLIF(h.total, 0)) * 100, 2) AS growth_percentage
FROM current_total c, historical_total h;
```

### Downloads Gained in the Last 18 Months

```sql
SELECT SUM(download_count) AS downloads_last_18_months
FROM npm_count.daily_downloads
WHERE date > CURRENT_DATE - INTERVAL '18 months';
```

---

## Time-Aggregated Queries

### Monthly Downloads (Last 24 Months)

```sql
SELECT 
    DATE_TRUNC('month', date) AS month,
    SUM(download_count) AS monthly_downloads
FROM npm_count.daily_downloads
WHERE date >= CURRENT_DATE - INTERVAL '24 months'
GROUP BY DATE_TRUNC('month', date)
ORDER BY month DESC;
```

### Quarterly Downloads (Last 2 Years)

```sql
SELECT 
    DATE_TRUNC('quarter', date) AS quarter,
    SUM(download_count) AS quarterly_downloads
FROM npm_count.daily_downloads
WHERE date >= CURRENT_DATE - INTERVAL '2 years'
GROUP BY DATE_TRUNC('quarter', date)
ORDER BY quarter DESC;
```

### Quarterly Downloads (All Time)

```sql
SELECT 
    DATE_TRUNC('quarter', date) AS quarter,
    SUM(download_count) AS quarterly_downloads
FROM npm_count.daily_downloads
GROUP BY DATE_TRUNC('quarter', date)
ORDER BY quarter;
```

### Yearly Downloads (All Time)

```sql
SELECT 
    EXTRACT(YEAR FROM date) AS year,
    SUM(download_count) AS yearly_downloads
FROM npm_count.daily_downloads
GROUP BY EXTRACT(YEAR FROM date)
ORDER BY year;
```

---

## Growth Analysis

### Cumulative Downloads Over Time (Quarterly)

Shows the running total of downloads at the end of each quarter.

```sql
SELECT 
    quarter,
    quarterly_downloads,
    SUM(quarterly_downloads) OVER (ORDER BY quarter) AS cumulative_total
FROM (
    SELECT 
        DATE_TRUNC('quarter', date) AS quarter,
        SUM(download_count) AS quarterly_downloads
    FROM npm_count.daily_downloads
    GROUP BY DATE_TRUNC('quarter', date)
) q
ORDER BY quarter;
```

### Quarter-over-Quarter Growth

```sql
WITH quarterly_data AS (
    SELECT 
        DATE_TRUNC('quarter', date) AS quarter,
        SUM(download_count) AS quarterly_downloads
    FROM npm_count.daily_downloads
    GROUP BY DATE_TRUNC('quarter', date)
)
SELECT 
    quarter,
    quarterly_downloads,
    LAG(quarterly_downloads) OVER (ORDER BY quarter) AS prev_quarter_downloads,
    quarterly_downloads - LAG(quarterly_downloads) OVER (ORDER BY quarter) AS growth_absolute,
    ROUND(
        ((quarterly_downloads - LAG(quarterly_downloads) OVER (ORDER BY quarter))::numeric 
        / NULLIF(LAG(quarterly_downloads) OVER (ORDER BY quarter), 0)) * 100, 
        2
    ) AS growth_percentage
FROM quarterly_data
ORDER BY quarter DESC;
```

### Year-over-Year Growth

```sql
WITH yearly_data AS (
    SELECT 
        EXTRACT(YEAR FROM date)::int AS year,
        SUM(download_count) AS yearly_downloads
    FROM npm_count.daily_downloads
    GROUP BY EXTRACT(YEAR FROM date)
)
SELECT 
    year,
    yearly_downloads,
    LAG(yearly_downloads) OVER (ORDER BY year) AS prev_year_downloads,
    yearly_downloads - LAG(yearly_downloads) OVER (ORDER BY year) AS growth_absolute,
    ROUND(
        ((yearly_downloads - LAG(yearly_downloads) OVER (ORDER BY year))::numeric 
        / NULLIF(LAG(yearly_downloads) OVER (ORDER BY year), 0)) * 100, 
        2
    ) AS growth_percentage
FROM yearly_data
ORDER BY year DESC;
```

---

## Category-Level Analysis

### Quarterly Downloads by Category

```sql
SELECT 
    DATE_TRUNC('quarter', dd.date) AS quarter,
    c.name AS category,
    SUM(dd.download_count) AS quarterly_downloads
FROM npm_count.daily_downloads dd
JOIN npm_count.package_category pc ON dd.package_name = pc.package_id
JOIN npm_count.category c ON pc.category_id = c.id
GROUP BY DATE_TRUNC('quarter', dd.date), c.name
ORDER BY quarter DESC, quarterly_downloads DESC;
```

### Category Growth (Current vs 18 Months Ago)

```sql
WITH current_totals AS (
    SELECT 
        c.name AS category,
        SUM(dd.download_count) AS total
    FROM npm_count.daily_downloads dd
    JOIN npm_count.package_category pc ON dd.package_name = pc.package_id
    JOIN npm_count.category c ON pc.category_id = c.id
    GROUP BY c.name
),
historical_totals AS (
    SELECT 
        c.name AS category,
        SUM(dd.download_count) AS total
    FROM npm_count.daily_downloads dd
    JOIN npm_count.package_category pc ON dd.package_name = pc.package_id
    JOIN npm_count.category c ON pc.category_id = c.id
    WHERE dd.date <= CURRENT_DATE - INTERVAL '18 months'
    GROUP BY c.name
)
SELECT 
    ct.category,
    COALESCE(ht.total, 0) AS downloads_18_months_ago,
    ct.total AS downloads_today,
    ct.total - COALESCE(ht.total, 0) AS growth_absolute,
    ROUND(
        ((ct.total - COALESCE(ht.total, 0))::numeric / NULLIF(ht.total, 0)) * 100, 
        2
    ) AS growth_percentage
FROM current_totals ct
LEFT JOIN historical_totals ht ON ct.category = ht.category
ORDER BY growth_absolute DESC;
```

---

## Package-Level Analysis

### Top Growing Packages (Last 18 Months)

```sql
SELECT 
    package_name,
    SUM(download_count) AS downloads_last_18_months
FROM npm_count.daily_downloads
WHERE date > CURRENT_DATE - INTERVAL '18 months'
GROUP BY package_name
ORDER BY downloads_last_18_months DESC
LIMIT 25;
```

### Package Growth Comparison

```sql
WITH current_totals AS (
    SELECT 
        package_name,
        SUM(download_count) AS total
    FROM npm_count.daily_downloads
    GROUP BY package_name
),
historical_totals AS (
    SELECT 
        package_name,
        SUM(download_count) AS total
    FROM npm_count.daily_downloads
    WHERE date <= CURRENT_DATE - INTERVAL '18 months'
    GROUP BY package_name
)
SELECT 
    ct.package_name,
    COALESCE(ht.total, 0) AS downloads_18_months_ago,
    ct.total AS downloads_today,
    ct.total - COALESCE(ht.total, 0) AS growth_absolute,
    ROUND(
        ((ct.total - COALESCE(ht.total, 0))::numeric / NULLIF(ht.total, 0)) * 100, 
        2
    ) AS growth_percentage
FROM current_totals ct
LEFT JOIN historical_totals ht ON ct.package_name = ht.package_name
ORDER BY growth_absolute DESC
LIMIT 50;
```

---

## Snapshot Queries

### Downloads at Specific Historical Points

Use this to get cumulative totals at various points in time for trend analysis.

```sql
WITH time_points AS (
    SELECT unnest(ARRAY[
        CURRENT_DATE,
        CURRENT_DATE - INTERVAL '3 months',
        CURRENT_DATE - INTERVAL '6 months',
        CURRENT_DATE - INTERVAL '12 months',
        CURRENT_DATE - INTERVAL '18 months',
        CURRENT_DATE - INTERVAL '24 months'
    ])::date AS snapshot_date
)
SELECT 
    tp.snapshot_date,
    (SELECT SUM(download_count) 
     FROM npm_count.daily_downloads 
     WHERE date <= tp.snapshot_date) AS cumulative_downloads
FROM time_points tp
ORDER BY tp.snapshot_date DESC;
```

### Weekly Downloads (Last 12 Weeks)

```sql
SELECT 
    DATE_TRUNC('week', date) AS week_start,
    SUM(download_count) AS weekly_downloads
FROM npm_count.daily_downloads
WHERE date >= CURRENT_DATE - INTERVAL '12 weeks'
GROUP BY DATE_TRUNC('week', date)
ORDER BY week_start DESC;
```

---

## Data Quality Checks

### Date Range of Available Data

```sql
SELECT 
    MIN(date) AS earliest_date,
    MAX(date) AS latest_date,
    COUNT(DISTINCT date) AS total_days,
    COUNT(DISTINCT package_name) AS total_packages
FROM npm_count.daily_downloads;
```

### Packages with Missing Recent Data

```sql
SELECT 
    p.package_name,
    p.last_fetched_date,
    MAX(dd.date) AS last_download_date
FROM npm_count.npm_package p
LEFT JOIN npm_count.daily_downloads dd ON p.package_name = dd.package_name
WHERE p.is_active = true
GROUP BY p.package_name, p.last_fetched_date
HAVING MAX(dd.date) < CURRENT_DATE - INTERVAL '7 days'
ORDER BY last_download_date;
```
