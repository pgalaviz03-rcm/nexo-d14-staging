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
-- Requires migration 003_manual_reviews; do not apply to the older cloud schema.
GRANT SELECT,INSERT ON topics,article_reviews,review_topics,review_changes TO nexo_app;
GRANT UPDATE(name,name_key,active,version) ON topics TO nexo_app;
GRANT UPDATE(status,note,version,reviewed_by,updated_at) ON article_reviews TO nexo_app;
GRANT DELETE ON review_topics TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE topics_id_seq,article_reviews_id_seq,review_changes_id_seq TO nexo_app;
-- Also requires migration 004_reports; version and release rows are append-only.
GRANT SELECT,INSERT ON reports,report_versions,report_releases TO nexo_app;
GRANT UPDATE(current_version) ON reports TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE reports_id_seq,report_versions_id_seq,report_releases_id_seq TO nexo_app;
-- Requires 005_pulse. Platform grants are provisioned outside the application.
GRANT SELECT ON platform_grants,platform_brand TO nexo_app;
GRANT SELECT,INSERT ON pulse_configs,pulse_actors,pulse_batches,pulse_documents,pulse_mentions,pulse_accounts,pulse_rules TO nexo_app;
GRANT UPDATE(territory,min_classified,version,connector) ON pulse_configs TO nexo_app;
GRANT UPDATE(name,kind,active,version) ON pulse_actors TO nexo_app;
GRANT UPDATE(views,interactions,collected_at) ON pulse_documents TO nexo_app;
GRANT UPDATE(sentiment,emotion,method,reviewed_by,version) ON pulse_mentions TO nexo_app;
GRANT UPDATE(active) ON pulse_rules TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE pulse_actors_id_seq,pulse_batches_id_seq,pulse_documents_id_seq,pulse_accounts_id_seq,pulse_rules_id_seq TO nexo_app;
-- Requires 006_delivery. Outbox remains simulation-only; no deletion rights.
GRANT SELECT,INSERT ON content_assessments,briefing_schedules,delivery_jobs TO nexo_app;
GRANT UPDATE(source_title,source_body,source_url,source_sha256,sentiment,emotion,mockery,reviewed_by,version,updated_at) ON content_assessments TO nexo_app;
GRANT UPDATE(channel,frequency,local_time,timezone,weekday,lookback_days,enabled,destination_ciphertext,version,updated_at) ON briefing_schedules TO nexo_app;
GRANT UPDATE(state) ON delivery_jobs TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE content_assessments_id_seq,delivery_jobs_id_seq TO nexo_app;

-- Requires 007_analysis. Runtime queues work only, never accepts model outputs.
GRANT SELECT,INSERT ON content_analyses TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE content_analyses_id_seq TO nexo_app;

-- Requires 008_actor_profiles. Project scope and owner fields stay immutable.
GRANT SELECT,INSERT ON actor_profiles TO nexo_app;
GRANT UPDATE(public_role,organization,territory,description,aliases_json,channels_json,version,updated_by,updated_at) ON actor_profiles TO nexo_app;

-- Requires 009_audience. Aggregate observations are append-only.
GRANT SELECT,INSERT ON audience_snapshots TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE audience_snapshots_id_seq TO nexo_app;

-- Requires 010_alerts. Findings and reviews are append-only.
GRANT SELECT,INSERT ON alert_incidents,alert_events TO nexo_app;
GRANT USAGE,SELECT ON SEQUENCE alert_incidents_id_seq,alert_events_id_seq TO nexo_app;
