# Power BI dashboard notes

The `.pbix` file isn't checked into the repo (binary, and typically too large
for git). Build it locally against the `insightiq` Postgres database and
export screenshots/a short recording for the portfolio README instead.

## Connection

Get Data > Database > PostgreSQL database
Server: localhost (or your host)
Database: insightiq

## Suggested pages

1. **Overview** — revenue trend, order volume trend, AOV KPI card
2. **Delivery performance** — SLA breach rate by state (map), avg delivery days by review score
3. **Product mix** — revenue by category, top products, category AOV comparison

## Suggested DAX measures

```
Total Revenue = SUM(fact_orders[price])

AOV = DIVIDE([Total Revenue], DISTINCTCOUNT(fact_orders[order_id]))

SLA Breach % =
DIVIDE(
    CALCULATE(COUNTROWS(fact_orders), fact_orders[delivered_date_key] > fact_orders[estimated_date_key]),
    COUNTROWS(fact_orders)
)

Repeat Customer Rate =
VAR CustomerOrderCounts =
    SUMMARIZE(fact_orders, dim_customer[customer_key], "Orders", DISTINCTCOUNT(fact_orders[order_id]))
VAR RepeatCustomers = COUNTROWS(FILTER(CustomerOrderCounts, [Orders] > 1))
VAR TotalCustomers = COUNTROWS(CustomerOrderCounts)
RETURN DIVIDE(RepeatCustomers, TotalCustomers)
```

## Publishing for the Streamlit embed

File > Publish to web (or use a Power BI embed token if this needs to stay
private) — paste the resulting URL into `app/streamlit_app.py`.
