// Actual PostgreSQL engine in WASM. Tests SQL policies, not network/TLS/pooling.
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const db = new PGlite();
await db.exec(await fs.readFile(process.argv[2], 'utf8'));
const tests=[];
async function check(name,fn){await fn();tests.push({test:name,status:'passed'});}
async function count(table){return (await db.query(`SELECT count(*)::int AS n FROM ${table}`)).rows[0].n;}
async function denied(sql){let failed=false;try{await db.exec(sql);}catch(e){failed=true;assert.ok(['42501','23503','23514'].includes(e.code),e.message);}assert.ok(failed,'Statement unexpectedly allowed');}
await db.exec(`INSERT INTO users(id,email,password_hash,active,auth_subject) VALUES
 (1,'alice@test.invalid','TEST',true,'11111111-1111-4111-8111-111111111111'),
 (2,'bob@test.invalid','TEST',true,'22222222-2222-4222-8222-222222222222'),
 (3,'viewer@test.invalid','TEST',true,'33333333-3333-4333-8333-333333333333');
 INSERT INTO projects(id,slug,name,status) VALUES(1,'d14','D14','active'),(2,'other','Other','active');
 INSERT INTO memberships(user_id,project_id,role) VALUES(1,1,'admin'),(2,2,'admin'),(3,1,'viewer');
 INSERT INTO section_metrics(project_id,section,election_year,nominal_list,territorial_votes,polling_places,null_votes,source)
 VALUES(1,146,2024,1104,630,2,41,'fixture'),(2,999,2024,100,50,1,0,'fixture');
 SET ROLE nexo_app;`);
await check('No actor sees zero private rows',async()=>assert.equal(await count('section_metrics'),0));
await db.exec("SELECT set_config('nexo.actor_id','1',false)");
await check('Alice sees only project A',async()=>{assert.equal(await count('section_metrics'),1);assert.equal((await db.query('SELECT section FROM section_metrics')).rows[0].section,146);});
await check('Cannot add membership',()=>denied("INSERT INTO memberships(user_id,project_id,role) VALUES(1,2,'admin')"));
await check('Cannot escalate membership',()=>denied("UPDATE memberships SET role='admin' WHERE user_id=3"));
await check('Cannot alter historical data',()=>denied('UPDATE section_metrics SET territorial_votes=1'));
await check('Cannot read another user password row',async()=>assert.equal((await db.query('SELECT * FROM users WHERE id=2')).rows.length,0));
await check('Cannot insert another project article',()=>denied("INSERT INTO news_articles(project_id,title,url,url_hash,publisher,abstract,origin) VALUES(2,'x','https://x.invalid','hash','x','','csv')"));
await check('Can add own project dataset and blob',async()=>{await db.exec("INSERT INTO datasets(id,project_id,uploaded_by,filename,media_type,sha256,size_bytes,status,record_count,detail,path) VALUES(1,1,1,'test.csv','.csv','hash',1,'staged',0,'','database'); INSERT INTO dataset_blobs(dataset_id,project_id,content) VALUES(1,1,'\\x61');");assert.equal(await count('dataset_blobs'),1);});
await check('Cannot alter feed URLs through DB role',()=>denied("UPDATE feed_sources SET url='https://other.invalid'"));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer reads historical data',async()=>assert.equal(await count('section_metrics'),1));
await check('Viewer cannot insert article',()=>denied("INSERT INTO news_articles(project_id,title,url,url_hash,publisher,abstract,origin) VALUES(1,'x','https://x.invalid','hash','x','','csv')"));
await check('Viewer cannot insert dataset',()=>denied("INSERT INTO datasets(project_id,uploaded_by,filename,media_type,sha256,size_bytes,status,record_count,detail,path) VALUES(1,3,'test.csv','.csv','h2',1,'staged',0,'','database')"));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Bob cannot see project A blob',async()=>assert.equal(await count('dataset_blobs'),0));
await check('Bob sees only project B',async()=>assert.equal((await db.query('SELECT section FROM section_metrics')).rows[0].section,999));
await check('Transaction-local actor is cleared on commit',async()=>{await db.exec("SELECT set_config('nexo.actor_id','',false); BEGIN; SELECT set_config('nexo.actor_id','1',true); COMMIT;");assert.equal(await count('section_metrics'),0);});

await db.exec(`RESET ROLE;
 INSERT INTO users(id,email,password_hash,active) VALUES(4,'analyst@test.invalid','TEST',true);
 INSERT INTO memberships(user_id,project_id,role) VALUES(4,1,'analyst');
 INSERT INTO news_articles(id,project_id,title,url,url_hash,publisher,abstract,origin) VALUES
 (101,1,'Own article','https://example.org/a','own-review','Fixture','','csv'),
 (201,2,'Foreign article','https://example.org/b','foreign-review','Fixture','','csv');
 INSERT INTO topics(id,project_id,name,name_key,active,version,created_by) VALUES
 (101,1,'Water','water',true,1,1),(201,2,'Other','other',true,1,2);
 INSERT INTO article_reviews(id,project_id,article_id,status,note,version,reviewed_by) VALUES
 (101,1,101,'needs_check','first',1,1),(201,2,201,'reviewed','foreign',1,2);
 INSERT INTO review_topics(review_id,topic_id,project_id) VALUES(101,101,1),(201,201,2);
 INSERT INTO review_changes(project_id,review_id,version,actor_id,snapshot) VALUES
 (1,101,1,1,'{"status":"needs_check","note":"first","topics":[]}'),
 (2,201,1,2,'{"status":"reviewed","note":"foreign","topics":[]}');
 SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false);`);
await check('No identity sees no manual-review data',async()=>{for(const table of ['topics','article_reviews','review_topics','review_changes'])assert.equal(await count(table),0);});
await db.exec("SELECT set_config('nexo.actor_id','1',false)");
await check('Own project manual-review data only',async()=>{for(const table of ['topics','article_reviews','review_topics','review_changes'])assert.equal(await count(table),1);});
await check('Cannot create foreign project topic',()=>denied("INSERT INTO topics(project_id,name,name_key,active,version,created_by) VALUES(2,'Injected','injected',true,1,1)"));
await check('Composite review FK rejects foreign article',()=>denied("INSERT INTO article_reviews(project_id,article_id,status,note,version,reviewed_by) VALUES(1,201,'reviewed','',1,1)"));
await check('Composite label FK rejects foreign topic',()=>denied("INSERT INTO review_topics(review_id,topic_id,project_id) VALUES(101,201,1)"));
await check('Runtime cannot move topic to another project',()=>denied('UPDATE topics SET project_id=2 WHERE id=101'));
await check('Runtime cannot update revision history',()=>denied("UPDATE review_changes SET snapshot='{}' WHERE review_id=101"));
await check('Runtime cannot delete revision history',()=>denied('DELETE FROM review_changes WHERE review_id=101'));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer can read own review history',async()=>assert.equal(await count('review_changes'),1));
await check('Viewer cannot create topic',()=>denied("INSERT INTO topics(project_id,name,name_key,active,version,created_by) VALUES(1,'Viewer','viewer',true,1,3)"));
await check('Viewer cannot change review',async()=>assert.equal((await db.query("UPDATE article_reviews SET note='forged' WHERE id=101 RETURNING id")).rows.length,0));
await check('Viewer cannot remove labels',async()=>assert.equal((await db.query('DELETE FROM review_topics WHERE review_id=101 RETURNING review_id')).rows.length,0));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst cannot manage topics',()=>denied("INSERT INTO topics(project_id,name,name_key,active,version,created_by) VALUES(1,'Analyst','analyst',true,1,4)"));
await check('Analyst can review and append own revision',async()=>{
 assert.equal((await db.query("UPDATE article_reviews SET note='second',version=2,reviewed_by=4 WHERE id=101 RETURNING id")).rows.length,1);
 await db.exec(`INSERT INTO review_changes(project_id,review_id,version,actor_id,snapshot) VALUES(1,101,2,4,'{"status":"needs_check","note":"second","topics":[]}')`);
 assert.equal(await count('review_changes'),2);
});
await check('Analyst cannot forge another reviewer identity',()=>denied(`INSERT INTO review_changes(project_id,review_id,version,actor_id,snapshot) VALUES(1,101,3,1,'{}')`));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Foreign admin cannot see own-project history',async()=>assert.equal((await db.query('SELECT * FROM review_changes WHERE review_id=101')).rows.length,0));

await db.exec(`RESET ROLE;
 INSERT INTO reports(id,project_id,current_version,created_by) VALUES(101,1,2,1),(102,1,1,1),(201,2,1,2);
 INSERT INTO report_versions(project_id,report_id,version,payload,sha256,created_by) VALUES
 (1,101,1,'{"title":"Published"}','hash1',1),(1,101,2,'{"title":"Draft"}','hash2',1),
 (1,102,1,'{"title":"Unreleased"}','hash3',1),(2,201,1,'{"title":"Foreign"}','hash4',2);
 INSERT INTO report_releases(project_id,report_id,version,published_by) VALUES(1,101,1,1);
 SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false);`);
await check('No identity sees no reports',async()=>{for(const table of ['reports','report_versions','report_releases'])assert.equal(await count(table),0);});
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer reads only released report snapshots',async()=>{assert.equal(await count('report_versions'),1);assert.equal((await db.query('SELECT version FROM report_versions')).rows[0].version,1);});
await check('Viewer cannot see an unreleased report',async()=>assert.equal((await db.query('SELECT id FROM reports WHERE id=102')).rows.length,0));
await check('Viewer cannot add a report',()=>denied("INSERT INTO reports(project_id,current_version,created_by) VALUES(1,1,3)"));
await check('Viewer cannot publish a report',()=>denied('INSERT INTO report_releases(project_id,report_id,version,published_by) VALUES(1,101,2,3)'));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst sees own-project drafts',async()=>assert.equal(await count('report_versions'),3));
await check('Analyst can append a report version',async()=>{await db.exec("INSERT INTO report_versions(project_id,report_id,version,payload,sha256,created_by) VALUES(1,102,2,'{}','analyst',4)");assert.equal(await count('report_versions'),4);});
await check('Analyst cannot publish',()=>denied('INSERT INTO report_releases(project_id,report_id,version,published_by) VALUES(1,101,2,4)'));
await check('Runtime cannot alter saved snapshots',()=>denied("UPDATE report_versions SET payload='{}' WHERE report_id=101"));
await check('Runtime cannot delete reports or snapshots',async()=>{await denied('DELETE FROM reports WHERE id=101');await denied('DELETE FROM report_versions WHERE report_id=101');});
await check('Cannot forge snapshot author',()=>denied("INSERT INTO report_versions(project_id,report_id,version,payload,sha256,created_by) VALUES(1,102,3,'{}','forged',1)"));
await db.exec("SELECT set_config('nexo.actor_id','1',false)");
await check('Composite version FK rejects a foreign report',()=>denied("INSERT INTO report_versions(project_id,report_id,version,payload,sha256,created_by) VALUES(1,201,2,'{}','foreign',1)"));
await check('Composite release FK rejects a foreign version',()=>denied('INSERT INTO report_releases(project_id,report_id,version,published_by) VALUES(1,201,1,1)'));
await check('Admin releases current own-project snapshot',async()=>{await db.exec('INSERT INTO report_releases(project_id,report_id,version,published_by) VALUES(1,101,2,1)');assert.equal(await count('report_releases'),2);});
await check('Release history cannot be rewritten',async()=>{await denied('UPDATE report_releases SET version=1 WHERE report_id=101');await denied('DELETE FROM report_releases WHERE report_id=101');});
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Foreign admin cannot read report snapshots',async()=>{assert.equal(await count('report_versions'),1);assert.equal((await db.query('SELECT * FROM report_versions WHERE report_id=101')).rows.length,0);});
await db.exec('RESET ROLE');
await check('All tenant and identity tables have forced RLS',async()=>{assert.equal((await db.query("SELECT count(*)::int AS n FROM pg_class WHERE relname IN ('users','memberships','projects','datasets','dataset_blobs','section_metrics','feed_sources','news_articles','audit_events','usage_counters','topics','article_reviews','review_topics','review_changes','reports','report_versions','report_releases','platform_grants','platform_brand','pulse_configs','pulse_actors','pulse_batches','pulse_documents','pulse_mentions','pulse_accounts','pulse_rules','content_assessments','briefing_schedules','delivery_jobs','content_analyses','actor_profiles','audience_snapshots','alert_incidents','alert_events') AND relrowsecurity AND relforcerowsecurity")).rows[0].n,34);});

await db.exec(`INSERT INTO platform_grants(user_id,active,scope_bindings) VALUES(1,true,'{}');
 INSERT INTO platform_brand(id,name,tagline) VALUES(1,'Test Brand','Public identity');
 INSERT INTO pulse_configs(project_id,territory,min_classified,version,connector) VALUES(1,'Area A',20,1,'{}'),(2,'Area B',20,1,'{}');
 INSERT INTO pulse_actors(id,project_id,name,kind,active,is_demo,version,created_by) VALUES
 (101,1,'Public A','primary',true,false,1,1),(102,1,'Demo A','primary',true,true,1,1),(201,2,'Public B','primary',true,false,1,2);
 INSERT INTO pulse_batches(id,project_id,provider,dataset_ref,sha256,is_demo,created_by) VALUES
 (101,1,'manual','test','hash',false,1),(102,1,'manual','demo','hash',true,1),(201,2,'manual','test','hash',false,2);
 INSERT INTO pulse_documents(id,project_id,batch_id,network,external_id,url,title,text,published_at,collected_at,is_demo) VALUES
 (101,1,101,'facebook','a','https://example.org/a','A','',now(),now(),false),
 (102,1,102,'facebook','demo','https://example.org/demo','Demo','',now(),now(),true),
 (201,2,201,'facebook','b','https://example.org/b','B','',now(),now(),false);
 INSERT INTO pulse_mentions(project_id,document_id,actor_id,is_demo,method,version) VALUES
 (1,101,101,false,'unclassified',0),(1,102,102,true,'synthetic_fixture:v1',0),(2,201,201,false,'unclassified',0);
 INSERT INTO pulse_accounts(id,project_id,actor_id,network,url,captured_at,metrics,is_demo,created_by) VALUES
 (101,1,101,'facebook','https://example.org/a',now(),'{}',false,1),(201,2,201,'facebook','https://example.org/b',now(),'{}',false,2);
 INSERT INTO pulse_rules(id,project_id,actor_id,name,metric,threshold,min_mentions,active,is_demo,created_by) VALUES
 (101,1,101,'Volume','mentions',20,20,true,false,1),(201,2,201,'Volume','mentions',20,20,true,false,2);
 SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false);`);
const tenant=['pulse_configs','pulse_actors','pulse_batches','pulse_documents','pulse_mentions','pulse_accounts','pulse_rules'];
await check('Pulse unauthenticated scope is empty',async()=>{for(const t of tenant)assert.equal(await count(t),0);});
await check('Only public branding is readable without identity',async()=>{assert.equal(await count('platform_brand'),1);assert.equal(await count('platform_grants'),0);});
await db.exec("SELECT set_config('nexo.actor_id','1',false)");
await check('Pulse all tables filter foreign project rows',async()=>{for(const t of tenant)assert.equal((await db.query(`SELECT count(*)::int n FROM ${t} WHERE project_id=2`)).rows[0].n,0);});
await check('Platform grant does not bypass RLS memberships',async()=>assert.equal((await db.query('SELECT count(*)::int n FROM projects WHERE id=2')).rows[0].n,0));
await check('Runtime cannot grant platform access',()=>denied("INSERT INTO platform_grants(user_id,active,scope_bindings) VALUES(3,true,'{}')"));
await check('Runtime cannot alter platform access',()=>denied('UPDATE platform_grants SET active=true'));
await check('Runtime cannot alter public brand',()=>denied("UPDATE platform_brand SET name='Forged'"));
await check('Runtime cannot move pulse data to another client',()=>denied('UPDATE pulse_actors SET project_id=2 WHERE id=101'));
await check('Runtime cannot rewrite source content',()=>denied("UPDATE pulse_documents SET text='Forged' WHERE id=101"));
await check('Runtime can update observed counters only',async()=>assert.equal((await db.query('UPDATE pulse_documents SET views=10 WHERE id=101 RETURNING id')).rows.length,1));
await check('Runtime cannot rewrite account history',()=>denied("UPDATE pulse_accounts SET metrics='{}' WHERE id=101"));
await check('Runtime cannot delete import batch evidence',()=>denied('DELETE FROM pulse_batches WHERE id=101'));
await check('Pulse composite actor FK rejects foreign client reference',()=>denied("INSERT INTO pulse_accounts(project_id,actor_id,network,url,captured_at,metrics,is_demo,created_by) VALUES(1,201,'x','https://example.org/x',now(),'{}',false,1)"));
await check('Pulse composite mode FK rejects demo to real reference',()=>denied("INSERT INTO pulse_accounts(project_id,actor_id,network,url,captured_at,metrics,is_demo,created_by) VALUES(1,102,'x','https://example.org/x',now(),'{}',false,1)"));
await check('Pulse composite document FK rejects demo mixing',()=>denied("INSERT INTO pulse_mentions(project_id,document_id,actor_id,is_demo,method,version) VALUES(1,102,101,false,'unclassified',0)"));
await check('Cannot forge pulse batch creator',()=>denied("INSERT INTO pulse_batches(project_id,provider,dataset_ref,sha256,is_demo,created_by) VALUES(1,'manual','bad','hash',false,2)"));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer can read project pulse data',async()=>assert.equal(await count('pulse_documents'),2));
await check('Viewer cannot see owner platform grant',async()=>assert.equal(await count('platform_grants'),0));
await check('Viewer cannot import source batch',()=>denied("INSERT INTO pulse_batches(project_id,provider,dataset_ref,sha256,is_demo,created_by) VALUES(1,'manual','bad','hash',false,3)"));
await check('Viewer cannot change classification',async()=>assert.equal((await db.query("UPDATE pulse_mentions SET sentiment='positive',reviewed_by=3 WHERE document_id=101 RETURNING actor_id")).rows.length,0));
await check('Viewer cannot configure actors',async()=>assert.equal((await db.query("UPDATE pulse_actors SET name='Forged' WHERE id=101 RETURNING id")).rows.length,0));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst may classify content as themselves',async()=>assert.equal((await db.query("UPDATE pulse_mentions SET sentiment='neutral',reviewed_by=4,method='human_review:v1',version=1 WHERE document_id=101 RETURNING actor_id")).rows.length,1));
await check('Analyst cannot forge reviewer identity',()=>denied("UPDATE pulse_mentions SET sentiment='positive',reviewed_by=1 WHERE document_id=101"));
await check('Analyst cannot configure rules',async()=>assert.equal((await db.query('UPDATE pulse_rules SET active=false WHERE id=101 RETURNING id')).rows.length,0));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Foreign client sees their own pulse data only',async()=>{assert.equal(await count('pulse_documents'),1);assert.equal((await db.query('SELECT project_id FROM pulse_documents')).rows[0].project_id,2);});
await db.exec('RESET ROLE');


await db.exec(`INSERT INTO content_assessments(id,project_id,news_id,is_demo,source_title,source_body,source_url,source_sha256,sentiment,emotion,mockery,reviewed_by,version,updated_at) VALUES
 (101,1,101,false,'Own article','','https://example.org/a','fixture','positive','joy',false,1,1,now()),
 (201,2,201,false,'Foreign article','','https://example.org/b','fixture','negative','anger',true,2,1,now());
 INSERT INTO briefing_schedules(project_id,user_id,channel,frequency,local_time,timezone,weekday,lookback_days,enabled,destination_ciphertext,version,updated_at) VALUES
 (1,1,'email','daily','07:00','America/Mexico_City',0,1,true,'encrypted-only',1,now()),
 (1,3,'telegram','daily','08:00','America/Mexico_City',0,1,false,'encrypted-only',1,now()),
 (2,2,'email','weekly','09:00','America/Mexico_City',0,7,true,'encrypted-only',1,now());
 INSERT INTO delivery_jobs(id,project_id,user_id,schedule_version,scheduled_for,report_id,report_version,channel,state,message,message_sha256,is_simulation,created_at)
 VALUES(101,1,1,1,now(),101,1,'email','blocked_provider','fixture','fixture',true,now());
 SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false);`);
await check('No identity sees no assessment or private delivery rows',async()=>{for(const t of ['content_assessments','briefing_schedules','delivery_jobs'])assert.equal(await count(t),0);});
await db.exec("SELECT set_config('nexo.actor_id','1',false)");
await check('Admin sees project assessments but only own preferences',async()=>{assert.equal(await count('content_assessments'),1);assert.equal(await count('briefing_schedules'),1);assert.equal((await db.query('SELECT user_id FROM briefing_schedules')).rows[0].user_id,1);});
await check('Cannot configure another user in same project',async()=>assert.equal((await db.query("UPDATE briefing_schedules SET local_time='10:00' WHERE user_id=3 RETURNING user_id")).rows.length,0));
await check('Cannot write another user schedule',()=>denied("INSERT INTO briefing_schedules(project_id,user_id,channel,frequency,local_time,timezone,weekday,lookback_days,enabled,destination_ciphertext,version,updated_at) VALUES(2,2,'email','daily','07:00','UTC',0,1,true,'fixture',1,now())"));
await check('Cannot reference foreign article in assessment',()=>denied("INSERT INTO content_assessments(project_id,news_id,is_demo,source_title,source_body,source_url,source_sha256,reviewed_by,version,updated_at) VALUES(1,201,false,'X','','https://example.org','fixture',1,1,now())"));
await check('Runtime cannot move assessment to another client',()=>denied('UPDATE content_assessments SET project_id=2 WHERE id=101'));
await check('Runtime cannot rewrite queued message',()=>denied("UPDATE delivery_jobs SET message='forged' WHERE id=101"));
await check('Runtime cannot create a real outbound job',()=>denied("INSERT INTO delivery_jobs(project_id,user_id,schedule_version,scheduled_for,channel,state,message,message_sha256,is_simulation,created_at) VALUES(1,1,1,now(),'email','blocked_provider','','',false,now())"));
await check('Outbox cannot bind an unreleased report',()=>denied("INSERT INTO delivery_jobs(project_id,user_id,schedule_version,scheduled_for,report_id,report_version,channel,state,message,message_sha256,is_simulation,created_at) VALUES(1,1,1,now()+interval '1 minute',102,2,'email','blocked_provider','fixture','fixture',true,now())"));
await check('Cannot delete private scheduling history',()=>denied('DELETE FROM delivery_jobs WHERE id=101'));
await check('Owner can cancel a simulated job only',async()=>assert.equal((await db.query("UPDATE delivery_jobs SET state='cancelled' WHERE id=101 RETURNING id")).rows.length,1));
await check('Cancelled job cannot be reactivated through runtime',()=>denied("UPDATE delivery_jobs SET state='blocked_provider' WHERE id=101"));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer sees only own delivery preference',async()=>{assert.equal(await count('briefing_schedules'),1);assert.equal(await count('delivery_jobs'),0);});
await check('Viewer can configure own preference',async()=>assert.equal((await db.query("UPDATE briefing_schedules SET local_time='08:30' WHERE user_id=3 RETURNING user_id")).rows.length,1));
await check('Viewer cannot classify content',async()=>assert.equal((await db.query("UPDATE content_assessments SET sentiment='negative',reviewed_by=3 WHERE id=101 RETURNING id")).rows.length,0));
await check('WhatsApp cannot be stored as enabled channel',()=>denied("UPDATE briefing_schedules SET channel='whatsapp' WHERE user_id=3"));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst can manually classify own project piece',async()=>assert.equal((await db.query("UPDATE content_assessments SET sentiment='neutral',reviewed_by=4,version=2 WHERE id=101 RETURNING id")).rows.length,1));
await check('Analyst cannot forge assessment reviewer',()=>denied('UPDATE content_assessments SET reviewed_by=1 WHERE id=101'));
await db.exec("RESET ROLE; DELETE FROM memberships WHERE user_id=1 AND project_id=1; SET ROLE nexo_app; SELECT set_config('nexo.actor_id','1',false)");
await check('Revoked project membership hides all private delivery rows',async()=>{assert.equal(await count('briefing_schedules'),0);assert.equal(await count('delivery_jobs'),0);});
await db.exec('RESET ROLE');


await db.exec(`INSERT INTO content_analyses(id,project_id,news_id,is_demo,source_title,source_body,source_url,source_sha256,contract_version,state,attempts,created_at) VALUES
 (101,1,101,false,'Own article','','https://example.org/a','fixture','content-v1','queued',0,now()),
 (201,2,201,false,'Foreign article','','https://example.org/b','fixture','content-v1','queued',0,now());
 SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false);`);
await check('No identity sees no AI analysis jobs',async()=>assert.equal(await count('content_analyses'),0));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst sees only own project analysis',async()=>{assert.equal(await count('content_analyses'),1);assert.equal((await db.query('SELECT project_id FROM content_analyses')).rows[0].project_id,1);});
const insertAI=(id,project,news,state="'queued'",sentiment='NULL',demo='false')=>`INSERT INTO content_analyses(id,project_id,news_id,is_demo,source_title,source_body,source_url,source_sha256,contract_version,state,attempts,sentiment,created_at) VALUES(${id},${project},${news},${demo},'Fixture','','https://example.org','new-${id}','content-v1',${state},0,${sentiment},now())`;
await check('Analyst may queue unclassified work only',async()=>{await db.exec(insertAI(102,1,101));assert.equal(await count('content_analyses'),2);});
await check('Runtime cannot insert completed AI output',()=>denied(insertAI(103,1,101,"'completed'","'positive'")));
await check('Runtime cannot prefill labels in queued task',()=>denied(insertAI(104,1,101,"'queued'","'positive'")));
await check('Cannot queue foreign client article',()=>denied(insertAI(105,1,201)));
await check('Cannot queue work in foreign project',()=>denied(insertAI(106,2,201)));
await check('Cannot queue demonstration as real AI work',()=>denied(insertAI(107,1,101,"'queued'",'NULL','true')));
await check('Runtime cannot forge AI labels by update',()=>denied("UPDATE content_analyses SET sentiment='positive',state='completed' WHERE id=101"));
await check('Runtime cannot delete AI history',()=>denied('DELETE FROM content_analyses WHERE id=101'));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer can read own project analysis progress',async()=>assert.equal(await count('content_analyses'),2));
await check('Viewer cannot queue analysis',()=>denied(insertAI(108,1,101)));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Another client sees only their analysis jobs',async()=>{assert.equal(await count('content_analyses'),1);assert.equal((await db.query('SELECT project_id FROM content_analyses')).rows[0].project_id,2);});
await db.exec("SELECT set_config('nexo.actor_id','1',false)");
await check('Revoked membership cannot read analysis jobs',async()=>assert.equal(await count('content_analyses'),0));
await db.exec('RESET ROLE');


await db.exec(`INSERT INTO pulse_actors(id,project_id,name,kind,active,is_demo,version,created_by) VALUES(202,2,'Another foreign actor','comparator',true,false,1,2);
 INSERT INTO actor_profiles(actor_id,project_id,is_demo,public_role,organization,territory,description,aliases_json,channels_json,version,updated_by,updated_at) VALUES
 (101,1,false,'Public role','Institution','Territory','','[]','[]',1,1,now()),
 (201,2,false,'Foreign role','','','','[]','[]',1,2,now());
 SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false);`);
await check('No identity sees no actor dossiers',async()=>assert.equal(await count('actor_profiles'),0));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Reader sees dossiers only in assigned project',async()=>{assert.equal(await count('actor_profiles'),1);assert.equal((await db.query('SELECT project_id FROM actor_profiles')).rows[0].project_id,1);});
await check('Reader cannot edit dossier',async()=>assert.equal((await db.query("UPDATE actor_profiles SET public_role='forged',updated_by=3 WHERE actor_id=101 RETURNING actor_id")).rows.length,0));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Consultor cannot change directory configuration',async()=>assert.equal((await db.query("UPDATE actor_profiles SET territory='forged',updated_by=4 WHERE actor_id=101 RETURNING actor_id")).rows.length,0));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Other client sees own dossier only',async()=>{assert.equal(await count('actor_profiles'),1);assert.equal((await db.query('SELECT actor_id FROM actor_profiles')).rows[0].actor_id,201);});
await check('Foreign manager cannot edit another project dossier',async()=>assert.equal((await db.query("UPDATE actor_profiles SET public_role='forged',updated_by=2 WHERE actor_id=101 RETURNING actor_id")).rows.length,0));
await check('Manager may edit own public dossier',async()=>assert.equal((await db.query("UPDATE actor_profiles SET public_role='Revised public role',updated_by=2,version=2 WHERE actor_id=201 RETURNING actor_id")).rows.length,1));
await check('Cannot forge dossier updater',()=>denied('UPDATE actor_profiles SET updated_by=1 WHERE actor_id=201'));
await check('Cannot move dossier to another project',()=>denied('UPDATE actor_profiles SET project_id=1 WHERE actor_id=201'));
await check('Cannot replace actor linkage',()=>denied('UPDATE actor_profiles SET actor_id=101 WHERE actor_id=201'));
await check('Cannot delete actor dossier history',()=>denied('DELETE FROM actor_profiles WHERE actor_id=201'));
await db.exec("RESET ROLE; INSERT INTO memberships(user_id,project_id,role) VALUES(1,1,'admin'); SET ROLE nexo_app; SELECT set_config('nexo.actor_id','1',false)");
const profileInsert=(actor,project,demo='false')=>`INSERT INTO actor_profiles(actor_id,project_id,is_demo,public_role,organization,territory,description,aliases_json,channels_json,version,updated_by,updated_at) VALUES(${actor},${project},${demo},'','','','','[]','[]',1,1,now())`;
await check('Dossier cannot reference foreign actor',()=>denied(profileInsert(202,1)));
await check('Dossier cannot use demo actor as real record',()=>denied(profileInsert(102,1)));
await db.exec('RESET ROLE');


const audienceInsert=(id,pid,actor,creator,participants=100,returning=60,base=120,demo='false')=>`INSERT INTO audience_snapshots(id,project_id,actor_id,is_demo,network,url,provider,measurement_id,contract_version,period_from,period_to,reference_from,reference_to,captured_at,participants,returning_count,reference_participants,created_by) VALUES(${id},${pid},${actor},${demo},'facebook','https://facebook.com/fixture','manual','fixture-v1','participating-accounts-v1','2026-10-08','2026-10-15','2026-10-01','2026-10-08','2026-10-16'::timestamptz+interval '${id} minute',${participants},${returning},${base},${creator})`;
await db.exec(audienceInsert(101,1,101,1));await db.exec(audienceInsert(201,2,201,2));
await db.exec("SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false)");
await check('No identity sees no aggregate audience rows',async()=>assert.equal(await count('audience_snapshots'),0));
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer sees own project aggregate rows only',async()=>{assert.equal(await count('audience_snapshots'),1);assert.equal((await db.query('SELECT project_id FROM audience_snapshots')).rows[0].project_id,1);});
await check('Viewer cannot import audience aggregates',()=>denied(audienceInsert(102,1,101,3)));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst may insert own project aggregate history',async()=>{await db.exec(audienceInsert(103,1,101,4));assert.equal(await count('audience_snapshots'),2);});
await check('Cannot forge aggregate creator',()=>denied(audienceInsert(104,1,101,1)));
await check('Cannot insert aggregates in foreign project',()=>denied(audienceInsert(105,2,201,4)));
await check('Cannot bind foreign actor to own aggregate',()=>denied(audienceInsert(106,1,201,4)));
await check('Cannot use demo actor for real audience',()=>denied(audienceInsert(107,1,102,4)));
await check('Cannot insert demo aggregate history',()=>denied(audienceInsert(108,1,102,4,100,60,120,'true')));
await check('Aggregate returning count cannot exceed participants',()=>denied(audienceInsert(109,1,101,4,50,60)));
await check('Aggregate returning count cannot exceed reference cohort',()=>denied(audienceInsert(110,1,101,4,100,60,50)));
await check('Cannot rewrite aggregate history',()=>denied('UPDATE audience_snapshots SET participants=999 WHERE id=101'));
await check('Cannot delete aggregate history',()=>denied('DELETE FROM audience_snapshots WHERE id=101'));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Other client sees only their aggregate audience',async()=>{assert.equal(await count('audience_snapshots'),1);assert.equal((await db.query('SELECT project_id FROM audience_snapshots')).rows[0].project_id,2);});
await db.exec("RESET ROLE; DELETE FROM memberships WHERE user_id=1 AND project_id=1; SET ROLE nexo_app; SELECT set_config('nexo.actor_id','1',false)");
await check('Revoked membership hides aggregate audience',async()=>assert.equal(await count('audience_snapshots'),0));
await db.exec('RESET ROLE');


await db.exec("INSERT INTO memberships(user_id,project_id,role) VALUES(1,1,'admin'); INSERT INTO pulse_rules(id,project_id,actor_id,name,metric,threshold,min_mentions,active,is_demo,created_by) VALUES(102,1,101,'Second real rule','mentions',20,20,true,false,1)");
const incidentInsert=(id,pid,actor,rule,creator,demo='false')=>`INSERT INTO alert_incidents(id,project_id,actor_id,rule_id,is_demo,network,period_from,period_to,snapshot_json,snapshot_sha256,created_by,created_at) VALUES(${id},${pid},${actor},${rule},${demo},'facebook','2026-10-19','2026-10-20'::timestamptz+interval '${id} minute','{}','fixture',${creator},now())`;
await db.exec(incidentInsert(101,1,101,101,1));await db.exec(incidentInsert(201,2,201,201,2));
const eventInsert=(id,pid,incident,version,prior,state,creator)=>`INSERT INTO alert_events(id,project_id,alert_id,version,previous_status,status,note,created_by,created_at) VALUES(${id},${pid},${incident},${version},'${prior}','${state}','fixture',${creator},now())`;
await db.exec("SET ROLE nexo_app; SELECT set_config('nexo.actor_id','',false)");
await check('No identity sees no alert evidence or review history',async()=>{assert.equal(await count('alert_incidents'),0);assert.equal(await count('alert_events'),0);});
await db.exec("SELECT set_config('nexo.actor_id','3',false)");
await check('Viewer reads own project incident only',async()=>{assert.equal(await count('alert_incidents'),1);assert.equal((await db.query('SELECT project_id FROM alert_incidents')).rows[0].project_id,1);});
await check('Viewer cannot record incidents',()=>denied(incidentInsert(102,1,101,101,3)));
await check('Viewer cannot review alerts',()=>denied(eventInsert(101,1,101,1,'open','acknowledged',3)));
await db.exec("SELECT set_config('nexo.actor_id','4',false)");
await check('Analyst may record own project incident',async()=>{await db.exec(incidentInsert(106,1,101,102,4));assert.equal(await count('alert_incidents'),2);});
await check('Cannot forge incident author',()=>denied(incidentInsert(107,1,101,102,1)));
await check('Alert ledger guard is enabled and has no elevated identity',async()=>assert.equal((await db.query("SELECT count(*)::int AS n FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid WHERE t.tgrelid='public.alert_events'::regclass AND t.tgname='nexo_alert_event_guard' AND t.tgenabled='O' AND NOT p.prosecdef AND NOT t.tgisinternal")).rows[0].n,1));
await check('Analyst may acknowledge own project incident',async()=>{await db.exec(eventInsert(101,1,101,1,'open','acknowledged',4));assert.equal(await count('alert_events'),1);});
await check('Cannot skip a review version',()=>denied(eventInsert(102,1,101,3,'acknowledged','resolved',4)));
await check('Cannot forge previous alert state',()=>denied(eventInsert(103,1,101,2,'open','resolved',4)));
await check('Cannot forge review author',()=>denied(eventInsert(104,1,101,2,'acknowledged','resolved',1)));
await check('Cannot attach foreign incident to own review',()=>denied(eventInsert(105,1,201,1,'open','resolved',4)));
await check('Cannot write review in another project',()=>denied(eventInsert(106,2,201,1,'open','resolved',4)));
await check('Allowed resolve transition appends without changing evidence',async()=>{await db.exec(eventInsert(107,1,101,2,'acknowledged','resolved',4));assert.equal(await count('alert_events'),2);});
await check('Closed alert cannot be acknowledged without reopening',()=>denied(eventInsert(108,1,101,3,'resolved','acknowledged',4)));
await check('Reopen transition appends next version',async()=>{await db.exec(eventInsert(109,1,101,3,'resolved','open',4));assert.equal(await count('alert_events'),3);});
await check('Cannot rewrite incident evidence',()=>denied("UPDATE alert_incidents SET snapshot_json='forged' WHERE id=101"));
await check('Cannot delete incident evidence',()=>denied('DELETE FROM alert_incidents WHERE id=101'));
await check('Cannot edit review history',()=>denied("UPDATE alert_events SET note='forged' WHERE id=101"));
await check('Cannot delete review history',()=>denied('DELETE FROM alert_events WHERE id=101'));
await check('Cannot bind incident to foreign actor and rule',()=>denied(incidentInsert(103,1,201,201,4)));
await check('Cannot bind an actor to another actor rule',()=>denied(incidentInsert(104,1,102,101,4)));
await check('Cannot record demo as real incident',()=>denied(incidentInsert(105,1,102,102,4,'true')));
await db.exec("SELECT set_config('nexo.actor_id','2',false)");
await check('Another client sees only own incidents and no foreign reviews',async()=>{assert.equal(await count('alert_incidents'),1);assert.equal(await count('alert_events'),0);});
await db.exec("RESET ROLE; DELETE FROM memberships WHERE user_id=1 AND project_id=1; SET ROLE nexo_app; SELECT set_config('nexo.actor_id','1',false)");
await check('Revoked membership hides incidents and their evidence history',async()=>{assert.equal(await count('alert_incidents'),0);assert.equal(await count('alert_events'),0);});
await db.exec('RESET ROLE');

console.log(JSON.stringify({engine:'PGlite PostgreSQL WASM',version:(await db.query('SELECT version()')).rows[0],tests},null,2));
await db.close();
