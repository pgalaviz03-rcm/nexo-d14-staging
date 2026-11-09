"""Read-only offline benchmark against operator-supplied project cases."""
import argparse,json,sqlite3,sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.evidence_search import retrieve_context
from app.retrieval_evaluation import RetrievalCase,evaluate

def run(database,uploads,cases):
    database=Path(database).resolve(strict=True);uploads=Path(uploads).resolve(strict=True)
    def connection():
        conn=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
        conn.execute('PRAGMA query_only=ON');return conn
    engine=create_engine('sqlite://',creator=connection)
    try:
        with Session(engine) as session:
            def query(case):
                return retrieve_context(session,case.project_id,case.question,uploads,limit=case.limit,
                    source_kind=case.source_kind,days=case.days,document_id=case.document_id)
            return evaluate(cases,query)
    finally:engine.dispose()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--uploads',type=Path,required=True);parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.cases.stat().st_size>256*1024:raise ValueError('Archivo de casos demasiado grande.')
    cases=[RetrievalCase.model_validate(c) for c in json.loads(args.cases.read_text(encoding='utf-8-sig'))]
    result=run(args.database,args.uploads,cases)
    if args.output.suffix.lower()!='.json' or args.output.resolve() in {args.database.resolve(),args.cases.resolve()} or args.output.resolve().is_relative_to(args.uploads.resolve()):
        raise ValueError('Guarda el resultado JSON fuera de la base, casos y documentos originales.')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(passed=result['passed'],cases=result['cases'],cases_passed=result['cases_passed'],read_only=True)))
    return 0 if result['passed'] else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        print('No se completó la evaluación. Revisa los casos y la ubicación de los archivos; no compartas claves.')
        raise SystemExit(2)
