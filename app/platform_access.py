"""Materialize explicit full-project memberships for active platform owners.

Existing project authorization remains the single read/write boundary, including
legacy routes. Bindings allow a local owner to restore prior roles on revocation.
"""
import json
from sqlalchemy import select
from .models import Project,Membership


def bind_projects(session,grant,projects=None):
    bindings=json.loads(grant.scope_bindings or '{}')
    for project in projects if projects is not None else session.scalars(select(Project).where(Project.status=='active')).all():
        member=session.scalar(select(Membership).where(Membership.project_id==project.id,Membership.user_id==grant.user_id))
        if not member:
            member=Membership(project_id=project.id,user_id=grant.user_id,role='admin');session.add(member);session.flush()
            bindings[str(member.id)]=None
        elif member.role!='admin':
            bindings.setdefault(str(member.id),member.role);member.role='admin'
    grant.scope_bindings=json.dumps(bindings,sort_keys=True)


def unbind_projects(session,grant):
    for key,previous in json.loads(grant.scope_bindings or '{}').items():
        member=session.get(Membership,int(key))
        if member and member.user_id==grant.user_id and member.role=='admin':
            if previous is None:session.delete(member)
            else:member.role=previous
    grant.scope_bindings='{}'
