-- DataGuard PostgreSQL Schema
-- Run this once to create (or recreate) the required tables.
-- The script is idempotent: it uses IF NOT EXISTS throughout.

-- ============================================================
-- Table: orders
-- Stores validated, transformed order records.
-- ============================================================
CREATE TABLE IF NOT EXISTS orders (
    order_id        VARCHAR(64)    PRIMARY KEY,
    customer_id     VARCHAR(64)    NOT NULL,
    order_date      DATE           NOT NULL,
    product         VARCHAR(255)   NOT NULL,
    quantity        INTEGER        NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12,2)  NOT NULL CHECK (unit_price >= 0),
    total_amount    NUMERIC(14,2)  NOT NULL,
    status          VARCHAR(32)    NOT NULL CHECK (status IN ('PENDING','SHIPPED','DELIVERED','CANCELLED')),
    source_file     VARCHAR(512),
    created_at      TIMESTAMP      NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP      NOT NULL DEFAULT NOW()
);

-- ============================================================
-- Table: pipeline_runs
-- Audit log for every ETL pipeline execution.
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id              VARCHAR(64)    PRIMARY KEY,
    source_file         VARCHAR(512)   NOT NULL,
    started_at          TIMESTAMP      NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMP,
    status              VARCHAR(32)    NOT NULL DEFAULT 'RUNNING'
                            CHECK (status IN ('RUNNING','SUCCESS','PARTIAL_SUCCESS','FAILED')),
    total_records       INTEGER        NOT NULL DEFAULT 0,
    accepted_records    INTEGER        NOT NULL DEFAULT 0,
    rejected_records    INTEGER        NOT NULL DEFAULT 0,
    inserted_records    INTEGER        NOT NULL DEFAULT 0,
    updated_records     INTEGER        NOT NULL DEFAULT 0,
    error_message       TEXT
);

-- ============================================================
-- Table: quarantined_records
-- Rejected records with rejection reasons, linked to a run.
-- ============================================================
CREATE TABLE IF NOT EXISTS quarantined_records (
    quarantine_id       SERIAL         PRIMARY KEY,
    run_id              VARCHAR(64)    NOT NULL REFERENCES pipeline_runs(run_id),
    source_file         VARCHAR(512)   NOT NULL,
    source_row_number   INTEGER        NOT NULL,
    raw_record          JSONB          NOT NULL,
    rejection_reasons   JSONB          NOT NULL,
    quarantined_at      TIMESTAMP      NOT NULL DEFAULT NOW()
);

-- Indexes for common dashboard queries
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status     ON pipeline_runs (status);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started    ON pipeline_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_quarantined_run_id       ON quarantined_records (run_id);
CREATE INDEX IF NOT EXISTS idx_orders_status            ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_order_date        ON orders (order_date);
