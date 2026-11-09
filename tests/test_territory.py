"""Reused historical routes: exact D14 figures, own-project reads and CSV."""
import csv,io,json
from pathlib import Path
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from app.models import SectionMetric
from test_manual_reviews import archive,endpoint

def history(a):
    a[2].slug='d14'
    original=json.loads((Path(__file__).resolve().parents[1]/'data/secciones_2024.json').read_text(encoding='utf-8'))
    for row in original.values():a[1].add(SectionMetric(project_id=a[2].id,section=row['id'],election_year=2024,nominal_list=row['ln'],
        territorial_votes=row['votes'],polling_places=row['boxes'],null_votes=row['nulls'],source='fixture from preserved public history'))
    a[1].add(SectionMetric(project_id=a[3].id,section=999,election_year=2024,nominal_list=100,territorial_votes=25,polling_places=1,null_votes=1,source='other project fixture'))
    a[1].commit()

def route(a,suffix,actor=0):return endpoint(a[0],'/api/projects/{pid}/'+suffix)(pid=a[2].id,user=a[4][actor],session=a[1])

def test_preserved_territorial_and_official_figures(archive):
    history(archive);p=route(archive,'summary');rows=route(archive,'sections')
    assert len(rows)==45 and p['sections']==45 and p['territorial_votes']==41984 and p['nominal_list']==65378
    assert p['official_votes']==41992 and not any(r['id']==999 for r in rows)

def test_reader_uses_same_history_and_csv(archive):
    history(archive);rows=route(archive,'sections',actor=2);response=route(archive,'sections/export',actor=2)
    records=list(csv.DictReader(io.StringIO(response.body.decode('utf-8-sig'))))
    assert len(rows)==len(records)==45 and sum(int(r['Votos territoriales']) for r in records)==41984
    assert sum(int(r['Lista nominal']) for r in records)==65378

@pytest.mark.parametrize('suffix',['summary','sections','sections/export'])
def test_foreign_membership_cannot_read_or_export_history(archive,suffix):
    history(archive)
    with pytest.raises(HTTPException) as e:route(archive,suffix,actor=3)
    assert e.value.status_code==404

def test_partial_or_changed_history_never_claims_official_conciliation(archive):
    history(archive);row=archive[1].scalar(select(SectionMetric).where(SectionMetric.project_id==archive[2].id))
    row.territorial_votes+=1;archive[1].commit()
    assert route(archive,'summary')['official_votes'] is None
