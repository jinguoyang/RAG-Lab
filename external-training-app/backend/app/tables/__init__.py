"""外部培训应用表定义。"""
import sqlalchemy as sa

metadata = sa.MetaData()

external_users = sa.Table(
    "external_users", metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("display_name", sa.String(length=128), nullable=False),
    sa.Column("employee_no", sa.String(length=64), nullable=True),
    sa.Column("role", sa.String(length=32), nullable=False, server_default="employee"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

platform_app_bindings = sa.Table(
    "platform_app_bindings", metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("platform_base_url", sa.String(length=512), nullable=False),
    sa.Column("platform_app_id", sa.String(length=36), nullable=False),
    sa.Column("platform_api_key_ref", sa.String(length=256), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_review_tasks = sa.Table(
    "training_review_tasks", metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("platform_draft_id", sa.String(length=36), nullable=True),
    sa.Column("platform_plan_id", sa.String(length=36), nullable=True),
    sa.Column("review_type", sa.String(length=32), nullable=False),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
    sa.Column("reviewer_id", sa.String(length=36), nullable=True),
    sa.Column("submitted_payload", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_class_sessions = sa.Table(
    "training_class_sessions", metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("external_user_id", sa.String(length=36), nullable=False),
    sa.Column("platform_session_id", sa.String(length=36), nullable=True),
    sa.Column("platform_plan_id", sa.String(length=36), nullable=True),
    sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
    sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_class_messages = sa.Table(
    "training_class_messages", metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("role", sa.String(length=16), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("platform_message_id", sa.String(length=36), nullable=True),
    sa.Column("ui_actions_json", sa.JSON(), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)

training_answer_records = sa.Table(
    "training_answer_records", metadata,
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("platform_question_id", sa.String(length=36), nullable=True),
    sa.Column("question_type", sa.String(length=32), nullable=True),
    sa.Column("selected_answer", sa.String(length=256), nullable=True),
    sa.Column("submitted_payload", sa.JSON(), nullable=True),
    sa.Column("score", sa.Numeric(10, 2), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)
