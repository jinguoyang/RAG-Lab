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
# NOTE: binding_revisions was renamed to chunk_revisions in 0031
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
    # 0024 -> 0031 renamed to chunk_revisions (was binding_revisions)
    ("chunk_revisions", "chunk_revision_id"),
    ("chunk_revisions", "binding_id"),
    ("chunk_revisions", "knowledge_base_id"),
    ("chunk_revisions", "document_id"),
    ("chunk_revisions", "document_version_id"),
    ("chunk_revisions", "parse_revision_id"),
    ("chunk_revisions", "created_by"),
    # 0025 -> 0031 renamed: binding_revision_id -> chunk_revision_id
    ("chunks", "chunk_revision_id"),
    ("chunks", "parse_revision_id"),
    ("chunks", "document_version_id"),
    # 0026 - chunks (audit fields added)
    ("chunks", "deleted_by"),
    ("chunks", "retired_by"),
    # 0027 -> 0031 renamed: active_binding_revision_id -> active_chunk_revision_id
    ("document_kb_bindings", "active_chunk_revision_id"),
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
    # 0031 - chunk_revisions (params added)
    ("chunk_revisions", "params"),
]


# All foreign key constraints involving UUID columns.
# Format: (name, source_table, target_table, [source_cols], [target_cols], ondelete_or_None)
# These must be dropped before UUID->VARCHAR conversion and re-added after.
# NOTE: Names reflect the state after migration 0031 (binding_revisions -> chunk_revisions rename)
ALL_FK_CONSTRAINTS = [
    # 0001 - users (self-referencing)
    ("fk_users_created_by", "users", "users", ["created_by"], ["user_id"], None),
    ("fk_users_updated_by", "users", "users", ["updated_by"], ["user_id"], None),
    ("fk_users_deleted_by", "users", "users", ["deleted_by"], ["user_id"], None),
    # 0001 - user_groups
    ("fk_user_groups_created_by", "user_groups", "users", ["created_by"], ["user_id"], None),
    ("fk_user_groups_updated_by", "user_groups", "users", ["updated_by"], ["user_id"], None),
    ("fk_user_groups_deleted_by", "user_groups", "users", ["deleted_by"], ["user_id"], None),
    # 0001 - user_group_members
    ("fk_user_group_members_group_id", "user_group_members", "user_groups", ["group_id"], ["group_id"], None),
    ("fk_user_group_members_user_id", "user_group_members", "users", ["user_id"], ["user_id"], None),
    ("fk_user_group_members_created_by", "user_group_members", "users", ["created_by"], ["user_id"], None),
    # 0002 - knowledge_bases
    ("fk_knowledge_bases_owner_id", "knowledge_bases", "users", ["owner_id"], ["user_id"], None),
    ("fk_knowledge_bases_created_by", "knowledge_bases", "users", ["created_by"], ["user_id"], None),
    ("fk_knowledge_bases_updated_by", "knowledge_bases", "users", ["updated_by"], ["user_id"], None),
    ("fk_knowledge_bases_deleted_by", "knowledge_bases", "users", ["deleted_by"], ["user_id"], None),
    # 0003 - stored_files
    ("fk_stored_files_created_by", "stored_files", "users", ["created_by"], ["user_id"], None),
    ("fk_stored_files_deleted_by", "stored_files", "users", ["deleted_by"], ["user_id"], None),
    # 0003 - documents
    ("fk_documents_kb_id", "documents", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_documents_created_by", "documents", "users", ["created_by"], ["user_id"], None),
    ("fk_documents_updated_by", "documents", "users", ["updated_by"], ["user_id"], None),
    ("fk_documents_deleted_by", "documents", "users", ["deleted_by"], ["user_id"], None),
    ("fk_documents_active_version_id", "documents", "document_versions", ["active_version_id"], ["version_id"], None),
    # 0003 - document_versions
    ("fk_document_versions_document_id", "document_versions", "documents", ["document_id"], ["document_id"], None),
    ("fk_document_versions_source_file_id", "document_versions", "stored_files", ["source_file_id"], ["file_id"], None),
    ("fk_document_versions_created_by", "document_versions", "users", ["created_by"], ["user_id"], None),
    ("fk_document_versions_updated_by", "document_versions", "users", ["updated_by"], ["user_id"], None),
    # 0003 - ingest_jobs
    ("fk_ingest_jobs_kb_id", "ingest_jobs", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_ingest_jobs_document_id", "ingest_jobs", "documents", ["document_id"], ["document_id"], None),
    ("fk_ingest_jobs_version_id", "ingest_jobs", "document_versions", ["version_id"], ["version_id"], None),
    ("fk_ingest_jobs_retry_of_job_id", "ingest_jobs", "ingest_jobs", ["retry_of_job_id"], ["job_id"], None),
    ("fk_ingest_jobs_created_by", "ingest_jobs", "users", ["created_by"], ["user_id"], None),
    # 0004 - config_templates
    ("fk_config_templates_created_by", "config_templates", "users", ["created_by"], ["user_id"], None),
    ("fk_config_templates_updated_by", "config_templates", "users", ["updated_by"], ["user_id"], None),
    ("fk_config_templates_deleted_by", "config_templates", "users", ["deleted_by"], ["user_id"], None),
    # 0004 - config_revisions
    ("fk_config_revisions_kb_id", "config_revisions", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_config_revisions_source_template_id", "config_revisions", "config_templates", ["source_template_id"], ["template_id"], None),
    ("fk_config_revisions_activated_by", "config_revisions", "users", ["activated_by"], ["user_id"], None),
    ("fk_config_revisions_deactivated_by", "config_revisions", "users", ["deactivated_by"], ["user_id"], None),
    ("fk_config_revisions_created_by", "config_revisions", "users", ["created_by"], ["user_id"], None),
    ("fk_config_revisions_updated_by", "config_revisions", "users", ["updated_by"], ["user_id"], None),
    ("fk_config_revisions_deleted_by", "config_revisions", "users", ["deleted_by"], ["user_id"], None),
    # 0004 - knowledge_bases (active_config_revision_id FK added in upgrade())
    ("fk_knowledge_bases_active_config_revision_id", "knowledge_bases", "config_revisions", ["active_config_revision_id"], ["config_revision_id"], None),
    # 0005 - qa_runs
    ("fk_qa_runs_kb_id", "qa_runs", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_qa_runs_config_revision_id", "qa_runs", "config_revisions", ["config_revision_id"], ["config_revision_id"], None),
    ("fk_qa_runs_source_run_id", "qa_runs", "qa_runs", ["source_run_id"], ["run_id"], None),
    ("fk_qa_runs_created_by", "qa_runs", "users", ["created_by"], ["user_id"], None),
    ("fk_qa_runs_updated_by", "qa_runs", "users", ["updated_by"], ["user_id"], None),
    # 0005 - qa_run_trace_steps
    ("fk_qa_run_trace_steps_run_id", "qa_run_trace_steps", "qa_runs", ["run_id"], ["run_id"], None),
    # 0005 - qa_run_candidates
    ("fk_qa_run_candidates_run_id", "qa_run_candidates", "qa_runs", ["run_id"], ["run_id"], None),
    # 0005 - qa_run_evidence
    ("fk_qa_run_evidence_run_id", "qa_run_evidence", "qa_runs", ["run_id"], ["run_id"], None),
    ("fk_qa_run_evidence_candidate_id", "qa_run_evidence", "qa_run_candidates", ["candidate_id"], ["candidate_id"], None),
    # 0005 - qa_run_citations
    ("fk_qa_run_citations_run_id", "qa_run_citations", "qa_runs", ["run_id"], ["run_id"], None),
    ("fk_qa_run_citations_evidence_id", "qa_run_citations", "qa_run_evidence", ["evidence_id"], ["evidence_id"], None),
    # 0006 - graph_snapshots
    ("fk_graph_snapshots_kb_id", "graph_snapshots", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_graph_snapshots_job_id", "graph_snapshots", "ingest_jobs", ["job_id"], ["job_id"], None),
    ("fk_graph_snapshots_created_by", "graph_snapshots", "users", ["created_by"], ["user_id"], None),
    ("fk_graph_snapshots_updated_by", "graph_snapshots", "users", ["updated_by"], ["user_id"], None),
    # 0006 - graph_chunk_refs
    ("fk_graph_chunk_refs_graph_snapshot_id", "graph_chunk_refs", "graph_snapshots", ["graph_snapshot_id"], ["graph_snapshot_id"], "CASCADE"),
    # 0007 - kb_member_bindings
    ("fk_kb_member_bindings_kb_id", "kb_member_bindings", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_kb_member_bindings_created_by", "kb_member_bindings", "users", ["created_by"], ["user_id"], None),
    ("fk_kb_member_bindings_updated_by", "kb_member_bindings", "users", ["updated_by"], ["user_id"], None),
    # 0008 - permissions
    ("fk_permissions_created_by", "permissions", "users", ["created_by"], ["user_id"], None),
    ("fk_permissions_updated_by", "permissions", "users", ["updated_by"], ["user_id"], None),
    # 0008 - role_permission_bindings (permission_code FK is non-UUID, excluded)
    ("fk_role_permission_bindings_created_by", "role_permission_bindings", "users", ["created_by"], ["user_id"], None),
    ("fk_role_permission_bindings_updated_by", "role_permission_bindings", "users", ["updated_by"], ["user_id"], None),
    # 0008 - acl_rules (permission_code FK is non-UUID, excluded)
    ("fk_acl_rules_created_by", "acl_rules", "users", ["created_by"], ["user_id"], None),
    ("fk_acl_rules_updated_by", "acl_rules", "users", ["updated_by"], ["user_id"], None),
    # 0009 - chunk_access_filters (permission_code FK is non-UUID, excluded)
    ("fk_chunk_access_filters_kb_id", "chunk_access_filters", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    # 0010 - audit_logs
    ("fk_audit_logs_actor_id", "audit_logs", "users", ["actor_id"], ["user_id"], None),
    ("fk_audit_logs_kb_id", "audit_logs", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_audit_logs_document_id", "audit_logs", "documents", ["document_id"], ["document_id"], None),
    # 0010 - chunks
    ("fk_chunks_version_id", "chunks", "document_versions", ["version_id"], ["version_id"], None),
    ("fk_chunks_document_id", "chunks", "documents", ["document_id"], ["document_id"], None),
    ("fk_chunks_kb_id", "chunks", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    # 0010 - chunk_access_filters (chunk FK added in upgrade())
    ("fk_chunk_access_filters_chunk_id", "chunk_access_filters", "chunks", ["chunk_id"], ["chunk_id"], "CASCADE"),
    # 0010 - index_sync_jobs
    ("fk_index_sync_jobs_kb_id", "index_sync_jobs", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_index_sync_jobs_created_by", "index_sync_jobs", "users", ["created_by"], ["user_id"], None),
    # 0010 - index_sync_records
    ("fk_index_sync_records_sync_job_id", "index_sync_records", "index_sync_jobs", ["sync_job_id"], ["sync_job_id"], "CASCADE"),
    # 0011 - evaluation_samples
    ("fk_evaluation_samples_kb_id", "evaluation_samples", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_evaluation_samples_source_run_id", "evaluation_samples", "qa_runs", ["source_run_id"], ["run_id"], None),
    ("fk_evaluation_samples_created_by", "evaluation_samples", "users", ["created_by"], ["user_id"], None),
    ("fk_evaluation_samples_updated_by", "evaluation_samples", "users", ["updated_by"], ["user_id"], None),
    ("fk_evaluation_samples_deleted_by", "evaluation_samples", "users", ["deleted_by"], ["user_id"], None),
    # 0012 - evaluation_runs
    ("fk_evaluation_runs_kb_id", "evaluation_runs", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_evaluation_runs_config_revision_id", "evaluation_runs", "config_revisions", ["config_revision_id"], ["config_revision_id"], None),
    ("fk_evaluation_runs_created_by", "evaluation_runs", "users", ["created_by"], ["user_id"], None),
    ("fk_evaluation_runs_updated_by", "evaluation_runs", "users", ["updated_by"], ["user_id"], None),
    ("fk_evaluation_runs_deleted_by", "evaluation_runs", "users", ["deleted_by"], ["user_id"], None),
    # 0012 - evaluation_results
    ("fk_evaluation_results_evaluation_run_id", "evaluation_results", "evaluation_runs", ["evaluation_run_id"], ["evaluation_run_id"], None),
    ("fk_evaluation_results_sample_id", "evaluation_results", "evaluation_samples", ["sample_id"], ["sample_id"], None),
    ("fk_evaluation_results_source_run_id", "evaluation_results", "qa_runs", ["source_run_id"], ["run_id"], None),
    ("fk_evaluation_results_actual_run_id", "evaluation_results", "qa_runs", ["actual_run_id"], ["run_id"], None),
    # 0014 - rag_apps
    ("fk_rag_apps_kb_id", "rag_apps", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_rag_apps_default_config_revision_id", "rag_apps", "config_revisions", ["default_config_revision_id"], ["config_revision_id"], None),
    ("fk_rag_apps_created_by", "rag_apps", "users", ["created_by"], ["user_id"], None),
    ("fk_rag_apps_updated_by", "rag_apps", "users", ["updated_by"], ["user_id"], None),
    ("fk_rag_apps_deleted_by", "rag_apps", "users", ["deleted_by"], ["user_id"], None),
    # 0014 - rag_app_api_keys
    ("fk_rag_app_api_keys_app_id", "rag_app_api_keys", "rag_apps", ["app_id"], ["app_id"], None),
    ("fk_rag_app_api_keys_created_by", "rag_app_api_keys", "users", ["created_by"], ["user_id"], None),
    ("fk_rag_app_api_keys_revoked_by", "rag_app_api_keys", "users", ["revoked_by"], ["user_id"], None),
    # 0014 - app_conversations
    ("fk_app_conversations_app_id", "app_conversations", "rag_apps", ["app_id"], ["app_id"], None),
    # 0014 - app_messages
    ("fk_app_messages_conversation_id", "app_messages", "app_conversations", ["conversation_id"], ["conversation_id"], None),
    ("fk_app_messages_qa_run_id", "app_messages", "qa_runs", ["qa_run_id"], ["run_id"], None),
    # 0014 - app_invocations
    ("fk_app_invocations_app_id", "app_invocations", "rag_apps", ["app_id"], ["app_id"], None),
    ("fk_app_invocations_api_key_id", "app_invocations", "rag_app_api_keys", ["api_key_id"], ["api_key_id"], None),
    ("fk_app_invocations_conversation_id", "app_invocations", "app_conversations", ["conversation_id"], ["conversation_id"], None),
    ("fk_app_invocations_message_id", "app_invocations", "app_messages", ["message_id"], ["message_id"], None),
    ("fk_app_invocations_qa_run_id", "app_invocations", "qa_runs", ["qa_run_id"], ["run_id"], None),
    # 0016 - system_dict_types
    ("fk_system_dict_types_created_by", "system_dict_types", "users", ["created_by"], ["user_id"], None),
    ("fk_system_dict_types_updated_by", "system_dict_types", "users", ["updated_by"], ["user_id"], None),
    ("fk_system_dict_types_deleted_by", "system_dict_types", "users", ["deleted_by"], ["user_id"], None),
    # 0016 - system_dict_items
    ("fk_system_dict_items_dict_type_id", "system_dict_items", "system_dict_types", ["dict_type_id"], ["dict_type_id"], None),
    ("fk_system_dict_items_created_by", "system_dict_items", "users", ["created_by"], ["user_id"], None),
    ("fk_system_dict_items_updated_by", "system_dict_items", "users", ["updated_by"], ["user_id"], None),
    ("fk_system_dict_items_deleted_by", "system_dict_items", "users", ["deleted_by"], ["user_id"], None),
    # 0017 - documents (owner_id FK added in upgrade())
    ("fk_documents_owner_id", "documents", "users", ["owner_id"], ["user_id"], None),
    # 0017 - document_kb_bindings
    ("fk_document_kb_bindings_document_id", "document_kb_bindings", "documents", ["document_id"], ["document_id"], None),
    ("fk_document_kb_bindings_kb_id", "document_kb_bindings", "knowledge_bases", ["kb_id"], ["kb_id"], None),
    ("fk_document_kb_bindings_version_id", "document_kb_bindings", "document_versions", ["version_id"], ["version_id"], None),
    ("fk_document_kb_bindings_created_by", "document_kb_bindings", "users", ["created_by"], ["user_id"], None),
    ("fk_document_kb_bindings_updated_by", "document_kb_bindings", "users", ["updated_by"], ["user_id"], None),
    # 0017 - library_parse_jobs
    ("fk_library_parse_jobs_document_id", "library_parse_jobs", "documents", ["document_id"], ["document_id"], None),
    ("fk_library_parse_jobs_version_id", "library_parse_jobs", "document_versions", ["version_id"], ["version_id"], None),
    ("fk_library_parse_jobs_created_by", "library_parse_jobs", "users", ["created_by"], ["user_id"], None),
    # 0019 - document_libraries
    ("fk_document_libraries_owner_id", "document_libraries", "users", ["owner_id"], ["user_id"], None),
    ("fk_document_libraries_created_by", "document_libraries", "users", ["created_by"], ["user_id"], None),
    ("fk_document_libraries_updated_by", "document_libraries", "users", ["updated_by"], ["user_id"], None),
    ("fk_document_libraries_deleted_by", "document_libraries", "users", ["deleted_by"], ["user_id"], None),
    # 0020 - library_member_bindings
    ("fk_library_member_bindings_library_id", "library_member_bindings", "document_libraries", ["library_id"], ["library_id"], None),
    ("fk_library_member_bindings_created_by", "library_member_bindings", "users", ["created_by"], ["user_id"], None),
    ("fk_library_member_bindings_updated_by", "library_member_bindings", "users", ["updated_by"], ["user_id"], None),
    # 0021 - documents (library_id FK added in upgrade())
    ("fk_documents_library_id", "documents", "document_libraries", ["library_id"], ["library_id"], None),
    # 0023 - parse_revisions (NOTE: PostgreSQL auto-generated name, not the explicit name from migration)
    ("parse_revisions_document_version_id_fkey", "parse_revisions", "document_versions", ["document_version_id"], ["version_id"], None),
    # 0024 -> 0031 renamed: chunk_revisions (was binding_revisions)
    ("fk_chunk_revisions_binding_id", "chunk_revisions", "document_kb_bindings", ["binding_id"], ["binding_id"], None),
    ("fk_chunk_revisions_knowledge_base_id", "chunk_revisions", "knowledge_bases", ["knowledge_base_id"], ["kb_id"], None),
    ("fk_chunk_revisions_document_id", "chunk_revisions", "documents", ["document_id"], ["document_id"], None),
    ("fk_chunk_revisions_document_version_id", "chunk_revisions", "document_versions", ["document_version_id"], ["version_id"], None),
    ("fk_chunk_revisions_parse_revision_id", "chunk_revisions", "parse_revisions", ["parse_revision_id"], ["parse_revision_id"], None),
    # 0025 -> 0031 renamed: chunks FKs
    ("fk_chunks_chunk_revision_id", "chunks", "chunk_revisions", ["chunk_revision_id"], ["chunk_revision_id"], None),
    ("fk_chunks_parse_revision_id", "chunks", "parse_revisions", ["parse_revision_id"], ["parse_revision_id"], None),
    ("fk_chunks_document_version_id", "chunks", "document_versions", ["document_version_id"], ["version_id"], None),
    # 0027 -> 0031 renamed: document_kb_bindings FK
    ("fk_document_kb_bindings_active_chunk_revision_id", "document_kb_bindings", "chunk_revisions", ["active_chunk_revision_id"], ["chunk_revision_id"], None),
]


def _drop_all_fks():
    """Drop all FK constraints that involve UUID columns."""
    for name, source_table, _, _, _, _ in ALL_FK_CONSTRAINTS:
        op.drop_constraint(name, source_table, type_="foreignkey")


def _create_all_fks():
    """Re-create all FK constraints after type conversion."""
    for name, source_table, target_table, source_cols, target_cols, ondelete in ALL_FK_CONSTRAINTS:
        kwargs = {}
        if ondelete:
            kwargs["ondelete"] = ondelete
        op.create_foreign_key(name, source_table, target_table, source_cols, target_cols, **kwargs)


def upgrade() -> None:
    # 1. Drop all FK constraints first (PostgreSQL can't have FK between UUID and VARCHAR)
    _drop_all_fks()

    # 2. UUID -> VARCHAR(36)
    for table, column in UUID_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.String(36),
            existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
            postgresql_using=f'"{column}"::varchar(36)',
        )

    # 3. Drop GIN index before JSONB->JSON (JSON doesn't support GIN)
    # 注意：此索引在 upgrade 中不会重建，因为 JSON 类型不支持 GIN 索引。
    # 如果需要对 scope 字段进行高效查询，应保持 JSONB 类型或使用 JSONB 运算符创建表达式索引。
    op.drop_index("idx_index_sync_jobs_scope", table_name="index_sync_jobs", if_exists=True)

    # 4. JSONB -> JSON
    for table, column in JSONB_COLUMNS:
        op.alter_column(
            table, column,
            type_=sa.JSON(),
            existing_type=sa.dialects.postgresql.JSONB(),
        )

    # 5. Re-create all FK constraints
    _create_all_fks()


def downgrade() -> None:
    # 1. Drop all FK constraints
    _drop_all_fks()

    # 2. Reverse: JSON -> JSONB
    for table, column in reversed(JSONB_COLUMNS):
        op.alter_column(
            table, column,
            type_=sa.dialects.postgresql.JSONB(),
            existing_type=sa.JSON(),
        )

    # 3. Re-create GIN index (now that column is JSONB again)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_index_sync_jobs_scope "
        "ON index_sync_jobs USING gin (scope)"
    )

    # 4. Reverse: VARCHAR(36) -> UUID
    for table, column in reversed(UUID_COLUMNS):
        op.alter_column(
            table, column,
            type_=sa.dialects.postgresql.UUID(as_uuid=True),
            existing_type=sa.String(36),
            postgresql_using=f'"{column}"::uuid',
        )

    # 5. Re-create all FK constraints
    _create_all_fks()
