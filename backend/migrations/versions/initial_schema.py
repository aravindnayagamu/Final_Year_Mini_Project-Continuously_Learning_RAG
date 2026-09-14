from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("paper_id", sa.String(64), primary_key=True, nullable=False),
        sa.Column("source_name", sa.String(128), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("retrieval_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_name", sa.String(256), nullable=True),
        sa.Column("vectorization_status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer, nullable=True),
        sa.Column("vectorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "query_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=True),
        sa.Column("context_chunks", sa.Integer, nullable=True),
        sa.Column("retrieval_time_ms", sa.Float, nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("triggered_by", sa.String(32), nullable=False, server_default="manual"),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="running"),
        sa.Column("articles_fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("articles_vectorized", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("query_logs")
    op.drop_table("documents")
