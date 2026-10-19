"""Query boundary and route-authorization tests without a local network dependency."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.models import Base, FeedSource, Membership, NewsArticle, Project, User
from app.news_review import article_record, documentary_brief, query_articles

NOW = datetime(2026, 10, 19, 22, 0, tzinfo=timezone.utc)


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv('NEXO_ENV', 'local')
    monkeypatch.setenv('NEXO_SECRET_KEY', 'candidate-test-' + 'x' * 48)
    app = create_app('sqlite:///' + str(tmp_path / 'news.db'), str(tmp_path / 'uploads'))
    with app.state.SessionLocal() as s:
        a = User(email='reader@test.local', password_hash='unused', active=True)
        b = User(email='other@test.local', password_hash='unused', active=True)
        p = Project(slug='a', name='A'); foreign = Project(slug='b', name='B')
        s.add_all([a, b, p, foreign]); s.flush()
        s.add_all([Membership(project_id=p.id, user_id=a.id, role='viewer'),
                   Membership(project_id=foreign.id, user_id=b.id, role='admin')])
        f = FeedSource(project_id=p.id, created_by=a.id, title='Medio A', url='https://example.org/feed')
        other_feed = FeedSource(project_id=foreign.id, created_by=b.id, title='Medio B', url='https://example.net/feed')
        s.add_all([f, other_feed]); s.flush()
        def add(title, project=p.id, feed=f.id, days=0, hours=0, missing=False, origin='rss'):
            moment = NOW - timedelta(days=days, hours=hours)
            row = NewsArticle(project_id=project, feed_id=feed, title=title,
                              url='https://example.org/' + str(len(s.new)) + title,
                              url_hash=str(len(s.new)) + title, publisher='Medio A',
                              abstract='', origin=origin,
                              published_at=None if missing else moment, ingested_at=moment)
            s.add(row)
        add('Hoy'); add('Limite 24h', days=1); add('Antigua', days=8)
        add('Sin fecha', hours=3, missing=True, feed=None, origin='csv')
        add('Futura', hours=-1)
        add('100% literal_\\', hours=2)
        add('Secreto externo', project=foreign.id, feed=other_feed.id)
        s.commit()
        yield app, s, a, b, p.id, foreign.id, f.id, other_feed.id
    app.state.engine.dispose()


def titles(s, p, **filters):
    return [row.title for row in s.scalars(query_articles(p, now=NOW, **filters))]


def test_time_boundary_fallback_and_future(database):
    _, s, _, _, p, *_ = database
    found = titles(s, p, days=1)
    assert set(found) == {'Hoy', 'Limite 24h', 'Sin fecha', '100% literal_\\'}
    assert found[0] == 'Hoy'
    assert 'Antigua' in titles(s, p)


def test_filters_cannot_cross_project(database):
    _, s, _, _, p, foreign, feed, other_feed = database
    assert titles(s, p, source_id=other_feed) == []
    assert titles(s, p, origin='csv') == ['Sin fecha']
    assert 'Sin fecha' not in titles(s, p, source_id=feed)
    assert titles(s, foreign) == ['Secreto externo']


@pytest.mark.parametrize('query', ['%', '_', '\\', '100%'])
def test_search_wildcards_are_literal(database, query):
    _, s, _, _, p, *_ = database
    assert titles(s, p, q=query) == ['100% literal_\\']


@pytest.mark.parametrize('filters', [{'days':2}, {'source_id':-1}, {'origin':'profile'}, {'q':'x'*101}])
def test_invalid_filters(database, filters):
    _, s, _, _, p, *_ = database
    with pytest.raises(ValueError):
        query_articles(p, **filters)


def test_brief_is_bounded_and_citations_are_original(database):
    _, s, _, _, p, *_ = database
    original = s.scalars(query_articles(p, now=NOW)).first()
    brief = documentary_brief([original] * 101, NOW, {'days':0})
    assert brief['selected_count'] == 100 and brief['truncated'] is True
    assert brief['ai_used'] is False
    assert brief['sources'] == [{'publisher':'Medio A', 'count':100}]
    assert brief['articles'][0]['url'] == original.url
    assert 'abstract' not in brief['articles'][0]
    assert brief['generated_at'].endswith('+00:00')
    assert article_record(original)['published_at'].endswith('+00:00')


@pytest.mark.parametrize('suffix', ['', '/brief'])
def test_routes_keep_membership_gate(database, suffix):
    app, s, a, b, p, foreign, feed, other_feed = database
    route = next(r.endpoint for r in app.routes if r.path == '/api/projects/{pid}/articles' + suffix)
    with pytest.raises(HTTPException) as rejected:
        route(pid=p, q='', days=0, source_id=0, origin='all', user=b, session=s)
    assert rejected.value.status_code == 404
    kwargs = dict(pid=p,q='',days=0,source_id=other_feed,origin='all',user=a,session=s)
    if suffix:
        result = route(**kwargs)
        assert result['selected_count'] == 0 and result['articles'] == []
    else:
        assert route(limit=100, **kwargs) == []


def test_empty_brief_is_not_an_invented_summary(database):
    brief = documentary_brief([], NOW, {'q':'no matching evidence'})
    assert brief['selected_count'] == 0
    assert brief['sources'] == brief['articles'] == []
    assert brief['truncated'] is False
