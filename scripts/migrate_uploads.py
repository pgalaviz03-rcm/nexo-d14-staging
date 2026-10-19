"""Move legacy filesystem uploads into PostgreSQL. Run offline as owner after backup."""
import os,sys,hashlib,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.database import create_database
from app.models import Dataset,DatasetBlob

def main():
    p=argparse.ArgumentParser();p.add_argument('--legacy-root',required=True,type=Path)
    a=p.parse_args();root=a.legacy_root.resolve(strict=True)
    engine,Session=create_database(os.environ['NEXO_MIGRATION_DATABASE_URL'])
    count=0
    with Session() as s:
        for d in s.scalars(select(Dataset).where(Dataset.path!='database')):
            file=Path(d.path).resolve(strict=True)
            if not file.is_relative_to(root):raise SystemExit('Ruta fuera del directorio autorizado')
            raw=file.read_bytes()
            if len(raw)!=d.size_bytes or len(raw)>12582912 or hashlib.sha256(raw).hexdigest()!=d.sha256:
                raise SystemExit('Integridad de archivo no coincide; transacción cancelada')
            if not s.get(DatasetBlob,d.id):s.add(DatasetBlob(dataset_id=d.id,project_id=d.project_id,content=raw))
            d.path='database';count+=1
        s.commit()
    print(f'Archivos migrados y verificados: {count}. Originales conservados.')

if __name__=='__main__':main()
