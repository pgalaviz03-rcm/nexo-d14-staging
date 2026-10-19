-- Restore-only grants after restoring public schema without ACLs.
-- Provision nexo_app before restore; restored policies refer to this role.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM nexo_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM nexo_app;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO nexo_app;
GRANT SELECT ON users,memberships,projects,datasets,dataset_blobs,section_metrics,feed_sources,news_articles,audit_events,usage_counters,alembic_version TO nexo_app;
GRANT INSERT ON datasets,dataset_blobs,feed_sources,news_articles,audit_events,usage_counters TO nexo_app;
GRANT UPDATE(status,last_error,last_checked_at) ON feed_sources TO nexo_app;
GRANT UPDATE(used) ON usage_counters TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE datasets_id_seq,feed_sources_id_seq,news_articles_id_seq,audit_events_id_seq,usage_counters_id_seq TO nexo_app;
