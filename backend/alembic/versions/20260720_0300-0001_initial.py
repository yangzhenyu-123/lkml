"""initial

Revision ID: 0001
Revises:
Create Date: 2026-07-20 03:00:00.000000

创建全部 9 张表（users / emails / analysis_jobs / stage_records / job_items /
daily_articles / subscriptions / opencode_configs / skill_configs）。
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # 2. emails
    op.create_table(
        "emails",
        sa.Column("message_id", sa.String(length=512), primary_key=True),
        sa.Column("in_reply_to", sa.String(length=512), nullable=True),
        sa.Column("subject", sa.String(length=1024), nullable=False),
        sa.Column("author", sa.String(length=255), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("patch_id", sa.String(length=64), nullable=True),
        sa.Column("refs", sa.JSON(), nullable=True),
        sa.Column("is_patch", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("subsystem", sa.String(length=64), nullable=True),
        sa.Column("raw_mbox_path", sa.String(length=512), nullable=True),
        sa.Column("reply_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_emails_in_reply_to", "emails", ["in_reply_to"])
    op.create_index("ix_emails_date", "emails", ["date"])
    op.create_index("ix_emails_patch_id", "emails", ["patch_id"])
    op.create_index("ix_emails_is_patch", "emails", ["is_patch"])
    op.create_index("ix_emails_subsystem", "emails", ["subsystem"])

    # 3. analysis_jobs
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("year_start", sa.Integer(), nullable=False),
        sa.Column("year_end", sa.Integer(), nullable=False),
        sa.Column("subsystem_filter", sa.String(length=255), nullable=True),
        sa.Column("keyword_filter", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("current_stage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_analysis_jobs_created_by"),
    )

    # 4. stage_records
    op.create_table(
        "stage_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("stage_no", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"], ["analysis_jobs.id"], ondelete="CASCADE", name="fk_stage_records_job_id"
        ),
    )
    op.create_index("ix_stage_records_job_id", "stage_records", ["job_id"])

    # 5. job_items（含自引用 FK，需单独创建索引）
    op.create_table(
        "job_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("stage_no", sa.Integer(), nullable=False),
        sa.Column("parent_item_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("email_message_id", sa.String(length=512), nullable=True),
        sa.Column("patch_id", sa.String(length=64), nullable=True),
        sa.Column("author", sa.String(length=255), nullable=True),
        sa.Column("subsystem", sa.String(length=64), nullable=True),
        sa.Column("optimization_type", sa.String(length=64), nullable=True),
        sa.Column("merged_upstream", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("output_path", sa.String(length=512), nullable=True),
        sa.Column("log_path", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("token_usage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["job_id"], ["analysis_jobs.id"], ondelete="CASCADE", name="fk_job_items_job_id"
        ),
        sa.ForeignKeyConstraint(
            ["parent_item_id"], ["job_items.id"], name="fk_job_items_parent_item_id"
        ),
    )
    op.create_index("ix_job_items_job_id", "job_items", ["job_id"])
    op.create_index("ix_job_items_stage_no", "job_items", ["stage_no"])

    # 6. daily_articles
    op.create_table(
        "daily_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_path", sa.String(length=512), nullable=True),
        sa.Column("subsystems", sa.JSON(), nullable=True),
        sa.Column("email_ids", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_daily_articles_date", "daily_articles", ["date"])

    # 7. subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("subsystem_filter", sa.String(length=255), nullable=True),
        sa.Column("email_notify", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("unsubscribe_token", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="fk_subscriptions_user_id"
        ),
        sa.UniqueConstraint("unsubscribe_token", name="uq_subscriptions_unsubscribe_token"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index(
        "ix_subscriptions_unsubscribe_token", "subscriptions", ["unsubscribe_token"]
    )

    # 8. opencode_configs（单例，id 恒为 1）
    op.create_table(
        "opencode_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("api_base", sa.String(length=512), nullable=True),
        sa.Column("api_key_enc", sa.String(length=1024), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("timeout", sa.Integer(), nullable=False, server_default="600"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="8192"),
        sa.Column("env_json", sa.JSON(), nullable=True),
        sa.Column("prompt_templates", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 9. skill_configs
    op.create_table(
        "skill_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("git_url", sa.String(length=512), nullable=True),
        sa.Column("branch", sa.String(length=64), nullable=True),
        sa.Column("local_path", sa.String(length=512), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("name", name="uq_skill_configs_name"),
    )
    op.create_index("ix_skill_configs_name", "skill_configs", ["name"])


def downgrade() -> None:
    op.drop_index("ix_skill_configs_name", table_name="skill_configs")
    op.drop_table("skill_configs")

    op.drop_table("opencode_configs")

    op.drop_index("ix_subscriptions_unsubscribe_token", table_name="subscriptions")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_daily_articles_date", table_name="daily_articles")
    op.drop_table("daily_articles")

    op.drop_index("ix_job_items_stage_no", table_name="job_items")
    op.drop_index("ix_job_items_job_id", table_name="job_items")
    op.drop_table("job_items")

    op.drop_index("ix_stage_records_job_id", table_name="stage_records")
    op.drop_table("stage_records")

    op.drop_table("analysis_jobs")

    op.drop_index("ix_emails_subsystem", table_name="emails")
    op.drop_index("ix_emails_is_patch", table_name="emails")
    op.drop_index("ix_emails_patch_id", table_name="emails")
    op.drop_index("ix_emails_date", table_name="emails")
    op.drop_index("ix_emails_in_reply_to", table_name="emails")
    op.drop_table("emails")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
