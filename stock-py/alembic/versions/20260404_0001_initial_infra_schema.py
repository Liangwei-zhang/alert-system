"""initial infra schema

Revision ID: 20260404_0001
Revises: None
Create Date: 2026-04-04 00:00:00
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260404_0001"
down_revision = None
branch_labels = None
depends_on = None


signal_type_enum = sa.Enum("buy", "sell", "split_buy", "split_sell", name="signaltype")
signal_status_enum = sa.Enum(
    "pending",
    "active",
    "triggered",
    "expired",
    "cancelled",
    name="signalstatus",
)
signal_validation_enum = sa.Enum("sfp", "choch", "fvg", "validated", name="signalvalidation")
trade_status_enum = sa.Enum(
    "pending", "confirmed", "adjusted", "ignored", "expired", name="tradestatus"
)
trade_action_enum = sa.Enum("buy", "sell", "add", name="tradeaction")
backtest_run_status_enum = sa.Enum(
    "pending", "running", "completed", "failed", name="backtestrunstatus"
)

metadata = sa.MetaData()

users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("email", sa.String(length=255), nullable=False, unique=True, index=True),
    sa.Column("name", sa.String(length=100), nullable=True),
    sa.Column("plan", sa.String(length=20), nullable=False, server_default=sa.text("'free'")),
    sa.Column("locale", sa.String(length=20), nullable=False, server_default=sa.text("'zh-CN'")),
    sa.Column(
        "timezone", sa.String(length=64), nullable=False, server_default=sa.text("'Asia/Shanghai'")
    ),
    sa.Column("extra", sa.JSON(), nullable=False),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

email_codes = sa.Table(
    "email_codes",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("email", sa.String(length=255), nullable=False, index=True),
    sa.Column("code", sa.String(length=6), nullable=False, index=True),
    sa.Column("ip", sa.String(length=64), nullable=True),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

sessions = sa.Table(
    "sessions",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True, index=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("device_info", sa.JSON(), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

user_account = sa.Table(
    "user_account",
    metadata,
    sa.Column(
        "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    ),
    sa.Column("total_capital", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
    sa.Column("currency", sa.String(length=10), nullable=False, server_default=sa.text("'USD'")),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

subscription_snapshots = sa.Table(
    "subscription_snapshots",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("snapshot", sa.JSON(), nullable=False),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

symbols = sa.Table(
    "symbols",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("symbol", sa.String(length=20), nullable=False, unique=True, index=True),
    sa.Column("name", sa.String(length=255), nullable=True),
    sa.Column("name_zh", sa.String(length=255), nullable=True),
    sa.Column("asset_type", sa.String(length=20), nullable=True),
    sa.Column("exchange", sa.String(length=50), nullable=True),
    sa.Column("sector", sa.String(length=100), nullable=True),
    sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

user_watchlist = sa.Table(
    "user_watchlist",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
    sa.Column("notify", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("min_score", sa.Integer(), nullable=False, server_default=sa.text("65")),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.UniqueConstraint("user_id", "symbol", name="uq_user_watchlist_symbol"),
)

user_portfolio = sa.Table(
    "user_portfolio",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
    sa.Column("shares", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("avg_cost", sa.Numeric(15, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("total_capital", sa.Numeric(15, 2), nullable=False, server_default=sa.text("0")),
    sa.Column("target_profit", sa.Numeric(8, 4), nullable=False, server_default=sa.text("0.15")),
    sa.Column("stop_loss", sa.Numeric(8, 4), nullable=False, server_default=sa.text("0.08")),
    sa.Column("notify", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    sa.Column("notes", sa.Text(), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.UniqueConstraint("user_id", "symbol", name="uq_user_portfolio_symbol"),
)

signals = sa.Table(
    "signals",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("stock_id", sa.Integer(), nullable=True, index=True),
    sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
    sa.Column("signal_type", signal_type_enum, nullable=False, index=True),
    sa.Column(
        "status",
        signal_status_enum,
        nullable=False,
        server_default=sa.text("'pending'"),
        index=True,
    ),
    sa.Column("entry_price", sa.Numeric(12, 4), nullable=False),
    sa.Column("stop_loss", sa.Numeric(12, 4), nullable=True),
    sa.Column("take_profit_1", sa.Numeric(12, 4), nullable=True),
    sa.Column("take_profit_2", sa.Numeric(12, 4), nullable=True),
    sa.Column("take_profit_3", sa.Numeric(12, 4), nullable=True),
    sa.Column("probability", sa.Float(), nullable=False, server_default=sa.text("0")),
    sa.Column("confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
    sa.Column("risk_reward_ratio", sa.Float(), nullable=True),
    sa.Column("sfp_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("chooch_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("fvg_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column(
        "validation_status", signal_validation_enum, nullable=False, server_default=sa.text("'sfp'")
    ),
    sa.Column("atr_value", sa.Numeric(12, 4), nullable=True),
    sa.Column("atr_multiplier", sa.Float(), nullable=False, server_default=sa.text("2")),
    sa.Column("indicators", sa.Text(), nullable=True),
    sa.Column("reasoning", sa.Text(), nullable=True),
    sa.Column(
        "generated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
    sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
)

scanner_runs = sa.Table(
    "scanner_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("bucket_id", sa.Integer(), nullable=False, index=True),
    sa.Column(
        "status",
        sa.String(length=32),
        nullable=False,
        server_default=sa.text("'running'"),
        index=True,
    ),
    sa.Column("scanned_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("emitted_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("suppressed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column(
        "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
)

scanner_decisions = sa.Table(
    "scanner_decisions",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("run_id", sa.Integer(), nullable=False, index=True),
    sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
    sa.Column("decision", sa.String(length=32), nullable=False, index=True),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("signal_type", sa.String(length=20), nullable=True),
    sa.Column("score", sa.Float(), nullable=True),
    sa.Column(
        "suppressed", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True
    ),
    sa.Column("dedupe_key", sa.String(length=255), nullable=True, index=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
)

notifications = sa.Table(
    "notifications",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("signal_id", sa.String(length=36), nullable=True, index=True),
    sa.Column("trade_id", sa.String(length=36), nullable=True, index=True),
    sa.Column("type", sa.String(length=50), nullable=False, index=True),
    sa.Column("title", sa.String(length=200), nullable=False),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
    sa.Column("metadata", sa.JSON(), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
)

push_subscriptions = sa.Table(
    "push_subscriptions",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("device_id", sa.String(length=120), nullable=False, index=True),
    sa.Column("endpoint", sa.String(length=4096), nullable=False),
    sa.Column(
        "provider", sa.String(length=20), nullable=False, server_default=sa.text("'webpush'")
    ),
    sa.Column("public_key", sa.String(length=2048), nullable=True),
    sa.Column("auth_key", sa.String(length=2048), nullable=True),
    sa.Column("user_agent", sa.String(length=512), nullable=True),
    sa.Column("locale", sa.String(length=32), nullable=True),
    sa.Column("timezone", sa.String(length=64), nullable=True),
    sa.Column("extra", sa.JSON(), nullable=False),
    sa.Column(
        "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"), index=True
    ),
    sa.Column(
        "last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.UniqueConstraint("user_id", "device_id", name="uq_push_subscription_user_device"),
)

message_outbox = sa.Table(
    "message_outbox",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("notification_id", sa.String(length=36), nullable=True, index=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("channel", sa.String(length=32), nullable=False, index=True),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column(
        "status",
        sa.String(length=32),
        nullable=False,
        server_default=sa.text("'pending'"),
        index=True,
    ),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

message_receipts = sa.Table(
    "message_receipts",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("notification_id", sa.String(length=36), nullable=False, index=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("ack_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("ack_deadline_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_delivery_channel", sa.String(length=32), nullable=True),
    sa.Column("last_delivery_status", sa.String(length=32), nullable=True),
    sa.Column("escalation_level", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column(
        "manual_follow_up_status",
        sa.String(length=32),
        nullable=False,
        server_default=sa.text("'none'"),
    ),
    sa.Column("manual_follow_up_updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

message_receipts_archive = sa.Table(
    "message_receipts_archive",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("notification_id", sa.String(length=36), nullable=False, index=True),
    sa.Column("user_id", sa.Integer(), nullable=False, index=True),
    sa.Column("ack_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    sa.Column("ack_deadline_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_delivery_channel", sa.String(length=32), nullable=True),
    sa.Column("last_delivery_status", sa.String(length=32), nullable=True),
    sa.Column("escalation_level", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column(
        "manual_follow_up_status",
        sa.String(length=32),
        nullable=False,
        server_default=sa.text("'none'"),
    ),
    sa.Column("manual_follow_up_updated_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

delivery_attempts = sa.Table(
    "delivery_attempts",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("receipt_id", sa.String(length=36), nullable=True, index=True),
    sa.Column("notification_id", sa.String(length=36), nullable=True, index=True),
    sa.Column("channel", sa.String(length=32), nullable=False, index=True),
    sa.Column("status", sa.String(length=32), nullable=False, index=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column(
        "attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

trade_log = sa.Table(
    "trade_log",
    metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column(
        "user_id",
        sa.Integer(),
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("symbol", sa.String(length=10), nullable=False, index=True),
    sa.Column("action", trade_action_enum, nullable=False, index=True),
    sa.Column("suggested_shares", sa.Numeric(15, 4), nullable=False),
    sa.Column("suggested_price", sa.Numeric(12, 4), nullable=False),
    sa.Column("suggested_amount", sa.Numeric(15, 2), nullable=False),
    sa.Column("actual_shares", sa.Numeric(15, 4), nullable=True),
    sa.Column("actual_price", sa.Numeric(12, 4), nullable=True),
    sa.Column("actual_amount", sa.Numeric(15, 2), nullable=True),
    sa.Column(
        "status", trade_status_enum, nullable=False, server_default=sa.text("'pending'"), index=True
    ),
    sa.Column("link_token", sa.String(length=64), nullable=False, unique=True, index=True),
    sa.Column("link_sig", sa.String(length=64), nullable=False),
    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("extra", sa.Text(), nullable=True),
    sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
)

sa.Index("ix_trade_log_user_status", trade_log.c.user_id, trade_log.c.status)
sa.Index("ix_trade_log_user_symbol", trade_log.c.user_id, trade_log.c.symbol)

ohlcv = sa.Table(
    "ohlcv",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column(
        "symbol_id",
        sa.Integer(),
        sa.ForeignKey("symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    ),
    sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
    sa.Column("timeframe", sa.String(length=16), nullable=False, index=True),
    sa.Column("bar_time", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("open", sa.Numeric(15, 6), nullable=False),
    sa.Column("high", sa.Numeric(15, 6), nullable=False),
    sa.Column("low", sa.Numeric(15, 6), nullable=False),
    sa.Column("close", sa.Numeric(15, 6), nullable=False),
    sa.Column("volume", sa.Numeric(20, 4), nullable=False, server_default=sa.text("0")),
    sa.Column("source", sa.String(length=50), nullable=True),
    sa.Column(
        "imported_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
    sa.UniqueConstraint(
        "symbol", "timeframe", "bar_time", name="uq_ohlcv_symbol_timeframe_bar_time"
    ),
)

ohlcv_anomalies = sa.Table(
    "ohlcv_anomalies",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("symbol", sa.String(length=20), nullable=False, index=True),
    sa.Column("timeframe", sa.String(length=16), nullable=False, index=True),
    sa.Column("bar_time", sa.DateTime(timezone=True), nullable=True, index=True),
    sa.Column("anomaly_code", sa.String(length=50), nullable=False, index=True),
    sa.Column(
        "severity",
        sa.String(length=20),
        nullable=False,
        server_default=sa.text("'warning'"),
        index=True,
    ),
    sa.Column("details", sa.Text(), nullable=True),
    sa.Column("source", sa.String(length=50), nullable=True),
    sa.Column(
        "quarantined_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
)

backtest_runs = sa.Table(
    "backtest_runs",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("strategy_name", sa.String(length=100), nullable=False, index=True),
    sa.Column("symbol", sa.String(length=20), nullable=True, index=True),
    sa.Column(
        "timeframe",
        sa.String(length=16),
        nullable=False,
        server_default=sa.text("'1d'"),
        index=True,
    ),
    sa.Column("window_days", sa.Integer(), nullable=False, server_default=sa.text("0"), index=True),
    sa.Column(
        "status",
        backtest_run_status_enum,
        nullable=False,
        server_default=sa.text("'pending'"),
        index=True,
    ),
    sa.Column("summary", sa.Text(), nullable=True),
    sa.Column("metrics", sa.Text(), nullable=True),
    sa.Column("evidence", sa.Text(), nullable=True),
    sa.Column("error_message", sa.Text(), nullable=True),
    sa.Column(
        "started_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
)

strategy_rankings = sa.Table(
    "strategy_rankings",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("strategy_name", sa.String(length=100), nullable=False, index=True),
    sa.Column(
        "timeframe",
        sa.String(length=16),
        nullable=False,
        server_default=sa.text("'1d'"),
        index=True,
    ),
    sa.Column("rank", sa.Integer(), nullable=False, index=True),
    sa.Column("score", sa.Float(), nullable=False, server_default=sa.text("0")),
    sa.Column("degradation", sa.Float(), nullable=False, server_default=sa.text("0")),
    sa.Column("symbols_covered", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("evidence", sa.Text(), nullable=True),
    sa.Column(
        "as_of_date",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
)

tradingagents_analysis_records = sa.Table(
    "tradingagents_analysis_records",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("request_id", sa.String(length=64), nullable=False, unique=True, index=True),
    sa.Column("job_id", sa.String(length=64), nullable=True, index=True),
    sa.Column("ticker", sa.String(length=10), nullable=False, index=True),
    sa.Column("analysis_date", sa.DateTime(timezone=True), nullable=False, index=True),
    sa.Column("selected_analysts", sa.Text(), nullable=True),
    sa.Column("trigger_type", sa.String(length=20), nullable=False, index=True),
    sa.Column("trigger_context", sa.Text(), nullable=True),
    sa.Column(
        "tradingagents_status",
        sa.String(length=20),
        nullable=False,
        server_default=sa.text("'pending'"),
        index=True,
    ),
    sa.Column("final_action", sa.String(length=20), nullable=True),
    sa.Column("decision_summary", sa.Text(), nullable=True),
    sa.Column("result_payload", sa.Text(), nullable=True),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("delayed_at", sa.DateTime(timezone=True), nullable=True, index=True),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
    sa.Column(
        "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
    ),
    sa.Column("poll_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    sa.Column("last_poll_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("webhook_received", sa.Boolean(), nullable=False, server_default=sa.text("false")),
)

sa.Index(
    "ix_ta_records_status_date",
    tradingagents_analysis_records.c.tradingagents_status,
    tradingagents_analysis_records.c.created_at,
)
sa.Index(
    "ix_ta_records_ticker_status",
    tradingagents_analysis_records.c.ticker,
    tradingagents_analysis_records.c.tradingagents_status,
)

tradingagents_submit_failures = sa.Table(
    "tradingagents_submit_failures",
    metadata,
    sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
    sa.Column("request_id", sa.String(length=64), nullable=False, index=True),
    sa.Column("ticker", sa.String(length=10), nullable=False),
    sa.Column("error_message", sa.Text(), nullable=False),
    sa.Column("error_code", sa.String(length=32), nullable=True),
    sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
    sa.Column(
        "resolved", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
        index=True,
    ),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True, index=True),
)

sa.Index(
    "ix_ta_failures_unresolved",
    tradingagents_submit_failures.c.resolved,
    tradingagents_submit_failures.c.next_retry_at,
)


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    metadata.drop_all(bind=bind)
    backtest_run_status_enum.drop(bind, checkfirst=True)
    trade_action_enum.drop(bind, checkfirst=True)
    trade_status_enum.drop(bind, checkfirst=True)
    signal_validation_enum.drop(bind, checkfirst=True)
    signal_status_enum.drop(bind, checkfirst=True)
    signal_type_enum.drop(bind, checkfirst=True)
