"""Normalize a downloaded export without network access. No authors retained."""
import argparse,json,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.apify_port import normalize_export,ImportBatch


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--mapping',type=Path,required=True)
    p.add_argument('--network',required=True);p.add_argument('--actor-id',type=int,action='append',required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--dataset-ref',default='')
    args=p.parse_args()
    if args.input.stat().st_size>2_000_000 or args.mapping.stat().st_size>10_000:raise ValueError('Archivo demasiado grande.')
    rows=normalize_export(json.loads(args.input.read_text(encoding='utf-8-sig')),
        json.loads(args.mapping.read_text(encoding='utf-8-sig')),network=args.network,actor_ids=args.actor_id,
        collected_at=datetime.now(timezone.utc))
    batch=ImportBatch(provider='apify_export',dataset_ref=args.dataset_ref,items=rows)
    with args.output.open('x',encoding='utf-8') as stream:stream.write(batch.model_dump_json(indent=2))
    print('Lote local normalizado. Revisar asignación de actores y procedencia antes de importarlo en el proyecto correcto.')


if __name__=='__main__':main()
