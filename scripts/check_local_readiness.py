"""Read-only local health and retrieval checks. No HTTP server or provider call."""
import argparse,ast,importlib.util,json,sqlite3,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluate_retrieval import run

def check(database,uploads,cases_path):
    code=Path(__file__).resolve().parents[1];database=Path(database).resolve(strict=True)
    checks=[]
    def record(name,passed,**details):checks.append(dict(check=name,passed=bool(passed),**details))
    missing=[name for name in ['fastapi','sqlalchemy','pydantic','pypdf','defusedxml','cryptography','jwt'] if importlib.util.find_spec(name) is None]
    record('runtime_dependencies',not missing,missing=missing)
    invalid=[]
    for p in sorted((code/'app').glob('*.py')):
        try:ast.parse(p.read_text(encoding='utf-8-sig'))
        except (SyntaxError,UnicodeError):invalid.append(p.name)
    record('application_syntax',not invalid,invalid=invalid)
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        record('sqlite_integrity',db.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
        record('foreign_keys',not db.execute('PRAGMA foreign_key_check').fetchone())
        roles=db.execute("select count(*) from memberships where role not in ('admin','editor','analyst','viewer')").fetchone()[0]
        record('membership_roles',roles==0)
        counts={table:db.execute('select count(*) from '+table).fetchone()[0] for table in
                ['projects','users','memberships','datasets','news_articles','section_metrics','reports','report_versions']}
    launcher=(code/'scripts/local_workspace.py').read_text(encoding='utf-8')
    flags=["NEXO_ENV='local'","NEXO_AI_ENABLED='false'","NEXO_OFFLINE='true'","host='127.0.0.1'"]
    record('offline_loopback_launcher',all(flag in launcher for flag in flags))
    if Path(cases_path).stat().st_size>256*1024:raise ValueError('Casos demasiado grandes.')
    cases=json.loads(Path(cases_path).read_text(encoding='utf-8-sig'))
    evaluated=run(database,uploads,cases)
    record('retrieval_evaluation',evaluated['passed'],cases=evaluated['cases'],cases_passed=evaluated['cases_passed'])
    return dict(contract='local-readiness-v1',date_utc=datetime.now(timezone.utc).isoformat(),
        ready_for_human_local_test=all(c['passed'] for c in checks),checks=checks,counts=counts,retrieval=evaluated,
        database_read_only=True,external_calls=0,ai_used=False,running_server_verified=False,
        production_ready=False,provider_connections_verified=False,
        pending=['Human general local acceptance','AI and API adapters/workers and real data validation',
                 'OCR for image-only files','Native PostgreSQL/RLS, cloud route activation and MFA',
                 'Independent offsite recovery and production operations'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--uploads',type=Path,required=True);parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    target=args.output.resolve()
    if target.suffix.lower()!='.json' or target in {args.database.resolve(),args.cases.resolve()} or target.is_relative_to(args.uploads.resolve()):
        raise ValueError('El resultado debe quedar separado de los datos originales.')
    result=check(args.database,args.uploads,args.cases);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Comprobación local aprobada. Puedes iniciar la prueba general.' if result['ready_for_human_local_test'] else
          'Hay comprobaciones pendientes. Conserva el archivo de resultados para revisarlo.')
    print('No se modificó la base, no se usó IA y no se conectó ningún proveedor.')
    return 0 if result['ready_for_human_local_test'] else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        print('No se completó la comprobación local. Revisa las rutas y el archivo de casos; no compartas claves.')
        raise SystemExit(2)
