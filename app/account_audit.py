"""Read-only audit of stored account references and aggregate snapshot contracts.

No fetching, identity certification, bot detection or personal profiling.
"""
from datetime import datetime, timedelta, timezone
import json
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .pulse_models import PulseActor, PulseAccount
from .actor_models import ActorProfile
from .actors_api import PublicChannel
from .network_service import COUNTERS, ACTIVITY, NETWORKS, aware, stamp, counter

MAX_ACTORS = 50
MAX_RECORDS = 1000
MAX_ACCOUNTS = 32
PROVIDERS = {'manual', 'apify_export'}


def safe_channel(network, url):
    try:
        return PublicChannel(network=network, url=url).url
    except (ValueError, TypeError):
        return None


def object_json(raw):
    if not isinstance(raw, str) or len(raw) > 32768:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (ValueError, TypeError, RecursionError):
        return None


def period_stamp(value):
    try:
        return stamp(value)
    except OverflowError:
        return None


def inspect_snapshot(row, now):
    """Only allowlisted fields leave this parser. Unknown JSON is never returned."""
    data = object_json(row.metrics)
    issues = set()
    captured = aware(row.captured_at)
    future = captured > now
    if future:
        issues.add('future_capture')
    if data is None:
        issues.add('invalid_payload')
        data = {}
    values = {k: counter(data.get(k)) for k in COUNTERS}
    invalid = [k for k in COUNTERS if data.get(k) is not None and values[k] is None]
    if invalid:
        issues.add('invalid_counter')
    if not any(v is not None for v in values.values()):
        issues.add('no_counters')
    provider = data.get('provider')
    provider = provider if isinstance(provider, str) and provider in PROVIDERS else None
    if provider is None:
        issues.add('unknown_origin')
    start, end = period_stamp(data.get('metrics_from')), period_stamp(data.get('metrics_to'))
    period_ok = bool(start and end and start < end <= captured)
    if any(data.get(k) is not None for k in ACTIVITY) and not period_ok:
        issues.add('invalid_period')
    return dict(id=row.id, at=captured, values=values, provider=provider,
                start=start, end=end, period_ok=period_ok, future=future,
                issues=issues, invalid=invalid)


def audit_accounts(session, pid, *, actor_id=0, network='all', start=None, end=None, now=None):
    now = aware(now or datetime.now(timezone.utc))
    end = end or now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = start or end - timedelta(days=7)
    if any(t.tzinfo is None or t.utcoffset() is None for t in (start, end)):
        raise HTTPException(422, 'Indica fechas con zona horaria.')
    start, end = aware(start), aware(end)
    if not timedelta(minutes=1) <= end-start <= timedelta(days=90) or end > now:
        raise HTTPException(422, 'El periodo debe ser de hasta 90 días y terminar antes de ahora.')
    if network not in NETWORKS or actor_id < 0:
        raise HTTPException(422, 'Filtro no admitido.')
    actors = session.scalars(select(PulseActor).where(PulseActor.project_id == pid,
        PulseActor.is_demo.is_(False)).order_by(PulseActor.active.desc(), PulseActor.name, PulseActor.id).limit(MAX_ACTORS+1)).all()
    bounded = len(actors) > MAX_ACTORS
    actors = actors[:MAX_ACTORS]
    if actor_id and not any(a.id == actor_id for a in actors):
        raise HTTPException(404, 'Actor no disponible en este corte del proyecto.')
    profiles = {p.actor_id: p for p in session.scalars(select(ActorProfile).where(
        ActorProfile.project_id == pid, ActorProfile.is_demo.is_(False),
        ActorProfile.actor_id.in_([a.id for a in actors]))).all()}
    items = []
    for actor in actors:
        if actor_id and actor.id != actor_id:
            continue
        profile = profiles.get(actor.id)
        refs, profile_issues = {}, set()
        try:
            channels = json.loads(profile.channels_json) if profile else []
            if not isinstance(channels, list) or len(channels) > 100:
                raise ValueError()
            for raw in channels:
                if not isinstance(raw, dict):
                    profile_issues.add('invalid_reference'); continue
                url = safe_channel(raw.get('network'), raw.get('url'))
                if not url:
                    profile_issues.add('invalid_reference'); continue
                key = (raw['network'], url)
                if key in refs:
                    profile_issues.add('duplicate_reference')
                refs[key] = dict(enabled=raw.get('enabled') is not False,
                                 reviewed=raw.get('review') == 'reviewed')
        except (ValueError, TypeError, RecursionError):
            profile_issues.add('invalid_reference')
        rows = session.scalars(select(PulseAccount).where(PulseAccount.project_id == pid,
            PulseAccount.actor_id == actor.id, PulseAccount.is_demo.is_(False)).order_by(
            PulseAccount.captured_at.desc(), PulseAccount.id.desc()).limit(MAX_RECORDS+1)).all()
        if len(rows) > MAX_RECORDS:
            bounded = True
        groups = {key: [] for key in refs}
        unsafe = 0
        for row in rows[:MAX_RECORDS]:
            url = safe_channel(row.network, row.url)
            if not url:
                unsafe += 1; continue
            groups.setdefault((row.network, url), []).append(inspect_snapshot(row, now))
        if unsafe:
            profile_issues.add('invalid_capture_reference')
        keys = sorted(groups, key=lambda k: (k not in refs, k))
        if len(keys) > MAX_ACCOUNTS:
            bounded = True
        for key in keys[:MAX_ACCOUNTS]:
            if network != 'all' and key[0] != network:
                continue
            history, ref = groups[key], refs.get(key)
            issues = set(profile_issues)
            for snapshot in history:
                issues.update(snapshot['issues'])
            if not ref:
                issues.add('unregistered_reference')
            elif not ref['reviewed']:
                issues.add('reference_unreviewed')
            eligible = [s for s in history if not s['future']]
            latest = eligible[0] if eligible else None
            current = next((s for s in eligible if s['period_ok'] and s['start'] == start and s['end'] == end
                            and any(s['values'][k] is not None for k in ACTIVITY)), None)
            previous = next((s for s in eligible if s['period_ok'] and s['start'] == start-(end-start)
                             and s['end'] == start and any(s['values'][k] is not None for k in ACTIVITY)), None)
            comparable = []
            if current and previous:
                if current['provider'] and current['provider'] == previous['provider']:
                    comparable = [k for k in ACTIVITY if current['values'][k] is not None and previous['values'][k] is not None]
                else:
                    issues.add('origin_mismatch')
            if history and not current:
                issues.add('no_period_capture')
            if latest and latest['at'] < start:
                issues.add('old_capture')
            if not actor.active or (ref and not ref['enabled']):
                state = 'paused'
            elif not ref:
                state = 'unregistered'
            elif not history:
                state = 'no_captures'
            elif comparable and not issues:
                state = 'ready'
            else:
                state = 'needs_review'
            fields = {k: ('invalid' if latest and k in latest['invalid'] else
                         'available' if latest and latest['values'][k] is not None else 'missing') for k in COUNTERS}
            items.append(dict(actor_id=actor.id, actor_name=actor.name, actor_active=actor.active,
                network=key[0], url=key[1], registered=bool(ref), enabled=actor.active and bool(ref and ref['enabled']),
                reference_reviewed=bool(ref and ref['reviewed']), state=state,
                captures_checked=len(history), latest_capture_at=latest['at'].isoformat() if latest else None,
                latest_origin=latest['provider'] if latest else None, fields=fields,
                period_capture_at=current['at'].isoformat() if current else None,
                previous_capture_at=previous['at'].isoformat() if previous else None,
                comparable_fields=comparable, issues=sorted(issues)))
        # Corrupt profiles/captures must remain visible even when there is no safe URL.
        if profile_issues and not groups and network == 'all':
            items.append(dict(actor_id=actor.id, actor_name=actor.name, actor_active=actor.active,
                network='other', url=None, registered=False, enabled=False, reference_reviewed=False,
                state='needs_review', captures_checked=unsafe, latest_capture_at=None, latest_origin=None,
                fields={k:'missing' for k in COUNTERS},period_capture_at=None,previous_capture_at=None,
                comparable_fields=[],issues=sorted(profile_issues)))
    return dict(project_id=pid, window=dict(start=start.isoformat(),end=end.isoformat()),
        generated_at=now.isoformat(), actors=[dict(id=a.id,name=a.name,active=a.active) for a in actors],
        selected_actor_id=actor_id, network=network, items=items,
        counts=dict(accounts=len(items),registered=sum(r['registered'] for r in items),
            with_captures=sum(r['latest_capture_at'] is not None for r in items),
            comparable=sum(bool(r['comparable_fields']) and r['enabled'] for r in items),
            pending=sum(r['state'] != 'ready' for r in items)),
        coverage_bounded=bounded, limits=dict(actors=MAX_ACTORS,captures_per_actor=MAX_RECORDS,accounts_per_actor=MAX_ACCOUNTS),
        method='account-data-quality-v1', external_calls=0)


def install_account_audit_api(app, db, current_user, allow):
    @app.get('/api/projects/{pid}/account-audit')
    def listing(pid:int,actor_id:int=0,network:str='all',start:datetime|None=None,end:datetime|None=None,
                user=Depends(current_user),session:Session=Depends(db)):
        allow(pid,user,session)
        return audit_accounts(session,pid,actor_id=actor_id,network=network,start=start,end=end)
