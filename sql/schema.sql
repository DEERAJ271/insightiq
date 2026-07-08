-- InsightIQ warehouse schema (star schema)
-- Adapt table/column names to whichever source dataset you use.

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key    SERIAL PRIMARY KEY,
    customer_id     VARCHAR(64) UNIQUE NOT NULL,
    city            VARCHAR(128),
    state           VARCHAR(64),
    country         VARCHAR(64) DEFAULT 'Brazil'
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_key     SERIAL PRIMARY KEY,
    product_id      VARCHAR(64) UNIQUE NOT NULL,
    category        VARCHAR(128),
    weight_g        NUMERIC,
    length_cm       NUMERIC,
    height_cm       NUMERIC,
    width_cm        NUMERIC
);

CREATE TABLE IF NOT EXISTS dim_seller (
    seller_key      SERIAL PRIMARY KEY,
    seller_id       VARCHAR(64) UNIQUE NOT NULL,
    city            VARCHAR(128),
    state           VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INT PRIMARY KEY,        -- YYYYMMDD
    full_date       DATE NOT NULL,
    year            INT,
    quarter         INT,
    month           INT,
    day             INT,
    day_of_week     INT,
    is_weekend      BOOLEAN
);

CREATE TABLE IF NOT EXISTS fact_orders (
    order_key           SERIAL PRIMARY KEY,
    order_id            VARCHAR(64) NOT NULL,
    customer_key        INT REFERENCES dim_customer(customer_key),
    product_key         INT REFERENCES dim_product(product_key),
    seller_key          INT REFERENCES dim_seller(seller_key),
    order_date_key      INT REFERENCES dim_date(date_key),
    delivered_date_key  INT REFERENCES dim_date(date_key),
    estimated_date_key  INT REFERENCES dim_date(date_key),
    order_status        VARCHAR(32),
    item_count          SMALLINT,
    price               NUMERIC(10, 2),
    freight_value       NUMERIC(10, 2),
    payment_type        VARCHAR(32),
    payment_installments INT,
    review_score        SMALLINT
);

CREATE INDEX IF NOT EXISTS idx_fact_orders_customer ON fact_orders(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_orders_product  ON fact_orders(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_orders_order_date ON fact_orders(order_date_key);

-- Business glossary table — this doubles as source material for the RAG index.
CREATE TABLE IF NOT EXISTS business_glossary (
    term            VARCHAR(128) PRIMARY KEY,
    definition      TEXT NOT NULL
);

INSERT INTO business_glossary (term, definition) VALUES
    ('AOV', 'Average order value: total revenue divided by number of orders.'),
    ('SLA breach', 'An order where the delivered date is later than the estimated delivery date.'),
    ('Repeat customer', 'A customer with more than one order in the dataset.')
ON CONFLICT (term) DO NOTHING;
