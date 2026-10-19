"""Bounded, project-scoped documentary queries. No sentiment or external AI calls."""
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from .models import NewsArticle


def query_articles(pid, q='', days=0, source_id=0, origin='all', *, now=None):
    if len(q) > 100:
        raise ValueError('Búsqueda máxima de 100 caracteres')
    if days not in {0, 1, 7, 30}:
        raise ValueError('Periodo permitido: 0, 1, 7 o 30 días')
    if source_id < 0:
        raise ValueError('Fuente inválida')
    if origin not in {'all', 'rss', 'csv'}:
        raise ValueError('Origen permitido: all, rss o csv')
    now = now or datetime.now(timezone.utc)
    stamp = func.coalesce(NewsArticle.published_at, NewsArticle.ingested_at)
    statement = select(NewsArticle).where(NewsArticle.project_id == pid)
    if q.strip():
        escaped = q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        token = '%' + escaped + '%'
        statement = statement.where(
            NewsArticle.title.ilike(token, escape='\\') |
            NewsArticle.abstract.ilike(token, escape='\\'))
    if days:
        statement = statement.where(stamp >= now - timedelta(days=days), stamp <= now)
    if source_id:
        statement = statement.where(NewsArticle.feed_id == source_id)
    if origin != 'all':
        statement = statement.where(NewsArticle.origin == origin)
    return statement.order_by(stamp.desc(), NewsArticle.id.desc())


def iso_utc(value):
    if value is None:
        return None
    # Local SQLite returns naive datetimes for values persisted in UTC.
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def article_record(row):
    return dict(id=row.id, title=row.title, url=row.url, publisher=row.publisher,
                feed_id=row.feed_id, abstract=row.abstract, origin=row.origin,
                published_at=iso_utc(row.published_at), ingested_at=iso_utc(row.ingested_at))


def documentary_brief(rows, now, filters):
    selected = rows[:100]
    counts = Counter(row.publisher for row in selected)
    return dict(
        generated_at=iso_utc(now), filters=filters, selected_count=len(selected),
        limit=100, truncated=len(rows) > 100, ai_used=False,
        scope_note=('Listado de publicaciones guardadas que coinciden con los filtros; '
                    'no es una encuesta, medición de ánimo ni verificación de hechos. '
                    'No acredita ubicación dentro del D14. Revisar cada fuente original. '
                    'Sin fecha de publicación, el periodo usa la fecha de ingreso.'),
        sources=[dict(publisher=name, count=count) for name, count in sorted(counts.items())],
        articles=[{key: value for key, value in article_record(row).items()
                   if key not in {'abstract', 'feed_id'}} for row in selected])
