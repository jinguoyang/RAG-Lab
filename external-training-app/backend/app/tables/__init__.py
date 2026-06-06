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

# ── Training Classroom ──────────────────────────────────────────────

training_classroom_sessions = sa.Table(
    "training_classroom_sessions", metadata,
    sa.Column("session_id", sa.String(length=36), primary_key=True),
    sa.Column("app_id", sa.String(length=36), nullable=False),
    sa.Column("plan_id", sa.String(length=36), nullable=True),
    sa.Column("end_user_id", sa.String(length=128), nullable=False),
    sa.Column("current_state", sa.String(length=32), nullable=False, server_default="INIT"),
    sa.Column("current_section_index", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("context_summary", sa.Text(), nullable=True),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.String(length=36), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", sa.String(length=36), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", sa.String(length=36), nullable=True),
)

training_classroom_messages = sa.Table(
    "training_classroom_messages", metadata,
    sa.Column("message_id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("role", sa.String(length=16), nullable=False),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("state_at_time", sa.String(length=32), nullable=True),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.String(length=36), nullable=True),
)

training_classroom_events = sa.Table(
    "training_classroom_events", metadata,
    sa.Column("event_id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("event_type", sa.String(length=32), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("result_state", sa.String(length=32), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="processed"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.String(length=36), nullable=True),
)

# ── Training Plans & Questions ─────────────────────────────────────

training_plans = sa.Table(
    "training_plans", metadata,
    sa.Column("plan_id", sa.String(length=36), primary_key=True),
    sa.Column("app_id", sa.String(length=36), nullable=False),
    sa.Column("job_title", sa.String(length=256), nullable=False),
    sa.Column("job_description", sa.Text(), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
    sa.Column("ability_groups", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("documents", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("recommend_reason", sa.Text(), nullable=True),
    sa.Column("reading_order", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.String(length=36), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", sa.String(length=36), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deleted_by", sa.String(length=36), nullable=True),
)

training_questions = sa.Table(
    "training_questions", metadata,
    sa.Column("question_id", sa.String(length=36), primary_key=True),
    sa.Column("plan_id", sa.String(length=36), nullable=False),
    sa.Column("app_id", sa.String(length=36), nullable=False),
    sa.Column("question_type", sa.String(length=32), nullable=False),
    sa.Column("category", sa.String(length=16), nullable=False, server_default="practice"),
    sa.Column("content", sa.Text(), nullable=False),
    sa.Column("options", sa.JSON(), nullable=True),
    sa.Column("correct_answer", sa.String(length=256), nullable=True),
    sa.Column("explanation", sa.Text(), nullable=True),
    sa.Column("rubric", sa.JSON(), nullable=True),
    sa.Column("evidence_chunk_ids", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
    sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("created_by", sa.String(length=36), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_by", sa.String(length=36), nullable=True),
)

training_question_appeals = sa.Table(
    "training_question_appeals", metadata,
    sa.Column("appeal_id", sa.String(length=36), primary_key=True),
    sa.Column("question_id", sa.String(length=36), nullable=False),
    sa.Column("end_user_id", sa.String(length=128), nullable=False),
    sa.Column("reason", sa.Text(), nullable=False),
    sa.Column("answer_record_id", sa.String(length=36), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
    sa.Column("resolution", sa.Text(), nullable=True),
    sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("resolved_by", sa.String(length=36), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

training_post_quizzes = sa.Table(
    "training_post_quizzes", metadata,
    sa.Column("quiz_id", sa.String(length=36), primary_key=True),
    sa.Column("session_id", sa.String(length=36), nullable=False),
    sa.Column("plan_id", sa.String(length=36), nullable=True),
    sa.Column("app_id", sa.String(length=36), nullable=False),
    sa.Column("end_user_id", sa.String(length=128), nullable=False),
    sa.Column("document_id", sa.String(length=128), nullable=False),
    sa.Column("questions", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("answers", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("results", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("score", sa.Numeric(10, 2), nullable=True),
    sa.Column("passed", sa.Boolean(), nullable=True),
    sa.Column("status", sa.String(length=16), nullable=False, server_default="started"),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)
