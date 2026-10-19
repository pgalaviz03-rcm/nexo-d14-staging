// Actual PostgreSQL engine in WASM. Tests SQL policies, not network/TLS/pooling.
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const db = new PGlite();
await db.exec(await fs.readFile(process.argv[2], 'utf8'));
const tests=[];
async function check(name,fn){await fn();tests.push({test:name,status:'passed'});}
async function count(table){return (await db.query(`SELECT count(*)::int AS n FROM ${table}`)).rows[0].n;}
async function denied(sql){let failed=false;try{await db.exec(sql);}catch(e){failed=true;assert.ok(['42501','23503'].includes(e.code),e.message);}assert.ok(failed,'Statement unexpectedly allowed');}
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
await db.exec('RESET ROLE');
await check('All tenant and identity tables have forced RLS',async()=>{assert.equal((await db.query("SELECT count(*)::int AS n FROM pg_class WHERE relname IN ('users','memberships','projects','datasets','dataset_blobs','section_metrics','feed_sources','news_articles','audit_events','usage_counters') AND relrowsecurity AND relforcerowsecurity")).rows[0].n,10);});
console.log(JSON.stringify({engine:'PGlite PostgreSQL WASM',version:(await db.query('SELECT version()')).rows[0],tests},null,2));
await db.close();
