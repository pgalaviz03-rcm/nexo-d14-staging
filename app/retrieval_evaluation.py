"""Declarative offline retrieval evaluation; never judges or generates an answer.

This is a local operator tool, not an API or a document-controlled agent.
Expectations must be reviewed by a person before serving as a quality baseline.
"""
import re
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from .knowledge import normalized

class ExpectedEvidence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_id:int|None=Field(default=None,ge=1)
    kind:Literal['news','document']|None=None
    page:int|None=Field(default=None,ge=1,le=160)
    row:int|None=Field(default=None,ge=1,le=5000)
    text:list[str]=Field(default_factory=list,max_length=8)

class RetrievalCase(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(pattern=r'^[a-zA-Z0-9_-]{1,60}$')
    project_id:int=Field(ge=1)
    question:str=Field(min_length=2,max_length=240)
    document_id:int|None=Field(default=None,ge=1)
    source_kind:Literal['all','news','documents']='documents'
    days:Literal[0,1,7,30]=0
    limit:int=Field(default=5,ge=1,le=8)
    expected:Literal['matches','no_matches','denied']='matches'
    evidence:list[ExpectedEvidence]=Field(default_factory=list,max_length=8)
    forbidden_sources:list[int]=Field(default_factory=list,max_length=20)
    max_results:int=Field(default=8,ge=0,le=8)

    @model_validator(mode='after')
    def meaningful(self):
        if self.expected=='matches' and not self.evidence:raise ValueError('Define la evidencia esperada.')
        if self.expected!='matches' and self.evidence:raise ValueError('Una ausencia o denegación no debe esperar citas.')
        if any(not 1<=len(t)<=240 for e in self.evidence for t in e.text):raise ValueError('Texto esperado fuera de límite.')
        return self

def source_id(citation):
    return citation.get('workbook_origin',{}).get('source_dataset_id',citation.get('dataset_id'))

def matches(citation,expected):
    return ((expected.source_id is None or source_id(citation)==expected.source_id)
        and (expected.kind is None or citation.get('kind')==expected.kind)
        and (expected.page is None or citation.get('page')==expected.page)
        and (expected.row is None or citation.get('workbook_origin',{}).get('row')==expected.row)
        and all(normalized(t) in normalized(citation.get('excerpt','')) for t in expected.text))

def evaluate(cases,retrieve):
    """Return identifiers/counts only. No questions or document excerpts in logs."""
    cases=[c if isinstance(c,RetrievalCase) else RetrievalCase.model_validate(c) for c in cases]
    if not 1<=len(cases)<=200 or len({c.id for c in cases})!=len(cases):raise ValueError('Usa de 1 a 200 casos con identificadores únicos.')
    results=[]
    for case in cases:
        errors=[];citations=[];bounded=False
        try:
            p=retrieve(case)
        except HTTPException as exc:
            if case.expected!='denied' or exc.status_code not in {403,404}:errors.append('unexpected_access_result')
        except Exception:
            errors.append('retrieval_error')
        else:
            citations=p.get('citations',[]);bounded=bool(p.get('coverage',{}).get('bounded'))
            if case.expected=='denied':errors.append('access_not_denied')
            if p.get('project_id')!=case.project_id or any(c.get('project_id')!=case.project_id for c in citations):errors.append('project_scope')
            if p.get('ai_used') is not False or p.get('external_calls')!=0 or p.get('answer') is not None:errors.append('offline_contract')
            if p.get('document_id')!=case.document_id:errors.append('document_filter')
            if case.document_id is not None and any(source_id(c)!=case.document_id for c in citations):errors.append('source_scope')
            if any(source_id(c) in case.forbidden_sources for c in citations):errors.append('forbidden_source')
            if len(citations)>min(case.max_results,case.limit):errors.append('result_limit')
            if len({c.get('citation') for c in citations})!=len(citations):errors.append('duplicate_citation')
            if any(not re.fullmatch('[a-f0-9]{64}',c.get('content_sha256','')) for c in citations):errors.append('citation_hash')
            if case.expected=='no_matches' and citations:errors.append('unexpected_match')
            if case.expected=='matches':
                if not citations:errors.append('missing_matches')
                if any(not any(matches(c,e) for c in citations) for e in case.evidence):errors.append('expected_evidence_missing')
        results.append(dict(id=case.id,passed=not errors,checks_failed=errors,citations=len(citations),bounded=bounded))
    return dict(contract='retrieval-evaluation-v1',passed=all(r['passed'] for r in results),cases=len(results),
        cases_passed=sum(r['passed'] for r in results),results=results,ai_used=False,external_calls=0,
        generation_evaluated=False,semantic_retrieval_evaluated=False)
