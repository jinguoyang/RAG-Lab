"""convert uuid and jsonb to generic types

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

# COMPLETE list of all UUID columns from all 32 migrations
# Format: (table_name, column_name)
UUID_COLUMNS = [
    # 0001 - users
    ("users", "user_id"),
    ("users", "created_by"),
    ("users", "updated_by"),
    ("users", "deleted_by"),
    # 0001 - user_groups
    ("user_groups", "group_id"),
    ("user_groups", "created_by"),
    ("user_groups", "updated_by"),
    ("user_groups", "deleted_by"),
    # 0001 - user_group_members
    ("user_group_members", "group_member_id"),
    ("user_group_members", "group_id"),
    ("user_group_members", "user_id"),
    ("user_group_members", "created_by"),
    # 0002 - knowledge_bases
    ("knowledge_bases", "kb_id"),
    ("knowledge_bases", "owner_id"),
    ("knowledge_bases", "active_config_revision_id"),
    ("knowledge_bases", "created_by"),
    ("knowledge_bases", "updated_by"),
    ("knowledge_bases", "deleted_by"),
    # 0003 - stored_files
    ("stored_files", "file_id"),
    ("stored_files", "created_by"),
    ("stored_files", "deleted_by"),
    # 0003 - documents
    ("documents", "document_id"),
    ("documents", "kb_id"),
    ("documents", "active_version_id"),
    ("documents", "created_by"),
    ("documents", "updated_by"),
    ("documents", "deleted_by"),
    # 0003 - document_versions
    ("document_versions", "version_id"),
    ("document_versions", "document_id"),
    ("document_versions", "source_file_id"),
    ("document_versions", "created_by"),
    ("document_versions", "updated_by"),
    # 0003 - ingest_jobs
    ("ingest_jobs", "job_id"),
    ("ingest_jobs", "kb_id"),
    ("ingest_jobs", "document_id"),
    ("ingest_jobs", "version_id"),
    ("ingest_jobs", "retry_of_job_id"),
    ("ingest_jobs", "created_by"),
    # 0004 - config_templates
    ("config_templates", "template_id"),
    ("config_templates", "created_by"),
    ("config_templates", "updated_by"),
    ("config_templates", "deleted_by"),
    # 0004 - config_revisions
    ("config_revisions", "config_revision_id"),
    ("config_revisions", "kb_id"),
    ("config_revisions", "source_template_id"),
    ("config_revisions", "activated_by"),
    ("config_revisions", "deactivated_by"),
    ("config_revisions", "created_by"),
    ("config_revisions", "updated_by"),
    ("config_revisions", "deleted_by"),
    # 0005 - qa_runs
    ("qa_runs", "run_id"),
    ("qa_runs", "kb_id"),
    ("qa_runs", "config_revision_id"),
    ("qa_runs", "source_run_id"),
    ("qa_runs", "created_by"),
    ("qa_runs", "updated_by"),
    # 0005 - qa_run_trace_steps
    ("qa_run_trace_steps", "trace_step_id"),
    ("qa_run_trace_steps", "run_id"),
    # 0005 - qa_run_candidates
    ("qa_run_candidates", "candidate_id"),
    ("qa_run_candidates", "run_id"),
    ("qa_run_candidates", "chunk_id"),
    # 0005 - qa_run_evidence
    ("qa_run_evidence", "evidence_id"),
    ("qa_run_evidence", "run_id"),
    ("qa_run_evidence", "chunk_id"),
    ("qa_run_evidence", "candidate_id"),
    # 0005 - qa_run_citations
    ("qa_run_citations", "citation_id"),
    ("qa_run_citations", "run_id"),
    ("qa_run_citations", "evidence_id"),
    # 0006 - graph_snapshots
    ("graph_snapshots", "graph_snapshot_id"),
    ("graph_snapshots", "kb_id"),
    ("graph_snapshots", "job_id"),
    ("graph_snapshots", "created_by"),
    ("graph_snapshots", "updated_by"),
    # 0006 - graph_chunk_refs
    ("graph_chunk_refs", "graph_chunk_ref_id"),
    ("graph_chunk_refs", "graph_snapshot_id"),
    ("graph_chunk_refs", "chunk_id"),
    # 0007 - kb_member_bindings
    ("kb_member_bindings", "binding_id"),
    ("kb_member_bindings", "kb_id"),
    ("kb_member_bindings", "subject_id"),
    ("kb_member_bindings", "created_by"),
    ("kb_member_bindings", "updated_by"),
    # 0008 - permissions
    ("permissions", "permission_id"),
    ("permissions", "created_by"),
    ("permissions", "updated_by"),
    # 0008 - role_permission_bindings
    ("role_permission_bindings", "role_permission_id"),
    ("role_permission_bindings", "created_by"),
    ("role_permission_bindings", "updated_by"),
    # 0008 - acl_rules
    ("acl_rules", "acl_rule_id"),
    ("acl_rules", "resource_id"),
    ("acl_rules", "subject_id"),
    ("acl_rules", "created_by"),
    ("acl_rules", "updated_by"),
    # 0009 - chunk_access_filters
    ("chunk_access_filters", "access_filter_id"),
    ("chunk_access_filters", "chunk_id"),
    ("chunk_access_filters", "kb_id"),
    # 0010 - audit_logs
    ("audit_logs", "audit_log_id"),
    ("audit_logs", "actor_id"),
    ("audit_logs", "resource_id"),
    ("audit_logs", "kb_id"),
    ("audit_logs", "document_id"),
    # 0010 - chunks
    ("chunks", "chunk_id"),
    ("chunks", "version_id"),
    ("chunks", "document_id"),
    ("chunks", "kb_id"),
    # 0010 - index_sync_jobs
    ("index_sync_jobs", "sync_job_id"),
    ("index_sync_jobs", "kb_id"),
    ("index_sync_jobs", "created_by"),
    # 0010 - index_sync_records
    ("index_sync_records", "sync_record_id"),
    ("index_sync_records", "sync_job_id"),
    ("index_sync_records", "resource_id"),
    # 0011 - evaluation_samples
    ("evaluation_samples", "sample_id"),
    ("evaluation_samples", "kb_id"),
    ("evaluation_samples", "source_run_id"),
    ("evaluation_samples", "created_by"),
    ("evaluation_samples", "updated_by"),
    ("evaluation_samples", "deleted_by"),
    # 0012 - evaluation_runs
    ("evaluation_runs", "evaluation_run_id"),
    ("evaluation_runs", "kb_id"),
    ("evaluation_runs", "config_revision_id"),
    ("evaluation_runs", "created_by"),
    ("evaluation_runs", "updated_by"),
    ("evaluation_runs", "deleted_by"),
    # 0012 - evaluation_results
    ("evaluation_results", "evaluation_result_id"),
    ("evaluation_results", "evaluation_run_id"),
    ("evaluation_results", "sample_id"),
    ("evaluation_results", "source_run_id"),
    ("evaluation_results", "actual_run_id"),
    # 0014 - rag_apps
    ("rag_apps", "app_id"),
    ("rag_apps", "kb_id"),
    ("rag_apps", "default_config_revision_id"),
    ("rag_apps", "created_by"),
    ("rag_apps", "updated_by"),
    ("rag_apps", "deleted_by"),
    # 0014 - rag_app_api_keys
    ("rag_app_api_keys", "api_key_id"),
    ("rag_app_api_keys", "app_id"),
    ("rag_app_api_keys", "created_by"),
    ("rag_app_api_keys", "revoked_by"),
    # 0014 - app_conversations
    ("app_conversations", "conversation_id"),
    ("app_conversations", "app_id"),
    # 0014 - app_messages
    ("app_messages", "message_id"),
    ("app_messages", "conversation_id"),
    ("app_messages", "qa_run_id"),
    # 0014 - app_invocations
    ("app_invocations", "invocation_id"),
    ("app_invocations", "app_id"),
    ("app_invocations", "api_key_id"),
    ("app_invocations", "conversation_id"),
    ("app_invocations", "message_id"),
    ("app_invocations", "qa_run_id"),
    # 0016 - system_dict_types
    ("system_dict_types", "dict_type_id"),
    ("system_dict_types", "created_by"),
    ("system_dict_types", "updated_by"),
    ("system_dict_types", "deleted_by"),
    # 0016 - system_dict_items
    ("system_dict_items", "dict_item_id"),
    ("system_dict_items", "dict_type_id"),
    ("system_dict_items", "created_by"),
    ("system_dict_items", "updated_by"),
    ("system_dict_items", "deleted_by"),
    # 0017 - documents (owner_id added)
    ("documents", "owner_id"),
    # 0017 - document_kb_bindings
    ("document_kb_bindings", "binding_id"),
    ("document_kb_bindings", "document_id"),
    ("document_kb_bindings", "kb_id"),
    ("document_kb_bindings", "version_id"),
    ("document_kb_bindings", "created_by"),
    ("document_kb_bindings", "updated_by"),
    # 0017 - library_parse_jobs
    ("library_parse_jobs", "job_id"),
    ("library_parse_jobs", "document_id"),
    ("library_parse_jobs", "version_id"),
    ("library_parse_jobs", "created_by"),
    # 0019 - document_libraries
    ("document_libraries", "library_id"),
    ("document_libraries", "owner_id"),
    ("document_libraries", "created_by"),
    ("document_libraries", "updated_by"),
    ("document_libraries", "deleted_by"),
    # 0020 - library_member_bindings
    ("library_member_bindings", "binding_id"),
    ("library_member_bindings", "library_id"),
    ("library_member_bindings", "subject_id"),
    ("library_member_bindings", "created_by"),
    ("library_member_bindings", "updated_by"),
    # 0021 - documents (library_id added)
    ("documents", "library_id"),
    # 0022 - document_versions (deleted_by added)
    ("document_versions", "deleted_by"),
    # 0023 - parse_revisions
    ("parse_revisions", "parse_revision_id"),
    ("parse_revisions", "document_version_id"),
    ("parse_revisions", "created_by"),
    ("parse_revisions", "deleted_by"),
    # 0024 - binding_revisions
    ("binding_revisions", "binding_revision_id"),
    ("binding_revisions", "binding_id"),
    ("binding_revisions", "knowledge_base_id"),
    ("binding_revisions", "document_id"),
    ("binding_revisions", "document_version_id"),
    ("binding_revisions", "parse_revision_id"),
    ("binding_revisions", "created_by"),
    # 0025 - chunks (new columns added)
    ("chunks", "binding_revision_id"),
    ("chunks", "parse_revision_id"),
    ("chunks", "document_version_id"),
    # 0026 - chunks (audit fields added)
    ("chunks", "deleted_by"),
    ("chunks", "retired_by"),
    # 0027 - document_kb_bindings (active_binding_revision_id added)
    ("document_kb_bindings", "active_binding_revision_id"),
]

# COMPLETE list of all JSONB columns from all 32 migrations
# Format: (table_name, column_name)
JSONB_COLUMNS = [
    # 0002 - knowledge_bases
    ("knowledge_bases", "metadata"),
    # 0003 - documents
    ("documents", "metadata"),
    # 0003 - document_versions
    ("document_versions", "metadata"),
    # 0003 - ingest_jobs
    ("ingest_jobs", "result_summary"),
    # 0004 - config_templates
    ("config_templates", "pipeline_definition"),
    ("config_templates", "default_params"),
    # 0004 - config_revisions
    ("config_revisions", "pipeline_definition"),
    ("config_revisions", "validation_snapshot"),
    # 0005 - qa_runs
    ("qa_runs", "override_snapshot"),
    ("qa_runs", "metrics"),
    # 0005 - qa_run_trace_steps
    ("qa_run_trace_steps", "input_summary"),
    ("qa_run_trace_steps", "output_summary"),
    ("qa_run_trace_steps", "metrics"),
    # 0005 - qa_run_candidates
    ("qa_run_candidates", "metadata"),
    # 0005 - qa_run_evidence
    ("qa_run_evidence", "source_snapshot"),
    # 0005 - qa_run_citations
    ("qa_run_citations", "location_snapshot"),
    # 0006 - graph_snapshots
    ("graph_snapshots", "source_scope"),
    # 0006 - graph_chunk_refs
    ("graph_chunk_refs", "metadata"),
    # 0009 - chunk_access_filters
    ("chunk_access_filters", "allow_subject_keys"),
    ("chunk_access_filters", "deny_subject_keys"),
    # 0010 - audit_logs
    ("audit_logs", "detail"),
    # 0010 - chunks
    ("chunks", "metadata"),
    # 0010 - index_sync_jobs
    ("index_sync_jobs", "scope"),
    # 0010 - index_sync_records
    ("index_sync_records", "provider_payload"),
    # 0011 - evaluation_samples
    ("evaluation_samples", "expected_evidence"),
    ("evaluation_samples", "metadata"),
    # 0012 - evaluation_runs
    ("evaluation_runs", "error_summary"),
    ("evaluation_runs", "metadata"),
    # 0012 - evaluation_results
    ("evaluation_results", "metrics"),
    # 0013 - qa_runs (columns added by 0013)
    ("qa_runs", "pipeline_snapshot"),
    ("qa_runs", "node_param_snapshot"),
    # 0014 - rag_apps
    ("rag_apps", "output_policy"),
    ("rag_apps", "metadata"),
    # 0014 - app_conversations
    ("app_conversations", "metadata"),
    # 0014 - app_messages
    ("app_messages", "metadata"),
    # 0014 - app_invocations
    ("app_invocations", "request_summary"),
    ("app_invocations", "response_summary"),
    # 0016 - system_dict_items
    ("system_dict_items", "extra"),
    # 0018 - library_parse_jobs (error_detail added)
    ("library_parse_jobs", "error_detail"),
    # 0023 - parse_revisions
    ("parse_revisions", "parse_options"),
]


def upgrade() -> None:
    # 1. UUID -> VARCHAR(36)
    for table, column in UUID_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.String(36),
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
            postgresql_using=f'"{column}"::varchar(36)',
        )

    # 2. JSONB -> JSON
    for table, column in JSONB_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.JSON(),
            existing_type=sa.dialects.postgresql.JSONB(),
        )

    # 3. Drop GIN index (if exists)
    op.drop_index("idx_index_sync_jobs_scope", table_name="index_sync_jobs", if_exists=True)


def downgrade() -> None:
    # Reverse: JSON -> JSONB
    for table, column in reversed(JSONB_COLUMNS):
        op.alter_column(
            table, column,
            type_=sa.dialects.postgresql.JSONB(),
            existing_type=sa.JSON(),
        )
    # Reverse: VARCHAR(36) -> UUID
    for table, column in reversed(UUID_COLUMNS):
        op.alter_column(
            table, column,
            type_=sa.dialects.postgresql.UUID(as_uuid=True),
            existing_type=sa.String(36),
            postgresql_using=f'"{column}"::uuid',
        )
