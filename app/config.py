"""Fail closed for cloud environments; no secrets are logged."""
import os
from urllib.parse import urlsplit
from sqlalchemy.engine import make_url


def cloud():
    return os.getenv('NEXO_ENV', 'local') in {'staging', 'production'}


def validate_config(db_url):
    if not cloud():
        return
    origin = urlsplit(os.getenv('NEXO_PUBLIC_ORIGIN', ''))
    issuer = urlsplit(os.getenv('NEXO_SUPABASE_URL', ''))
    if origin.scheme != 'https' or not origin.hostname or origin.path not in ('', '/') or origin.username or origin.password or origin.query or origin.fragment:
        raise RuntimeError('Configura NEXO_PUBLIC_ORIGIN HTTPS exacto')
    if issuer.scheme != 'https' or not issuer.hostname or not issuer.hostname.endswith('.supabase.co') or issuer.path not in ('', '/') or issuer.username or issuer.password or issuer.query or issuer.fragment or issuer.port not in (None,443):
        raise RuntimeError('Configura la URL del proyecto Supabase')
    if not os.getenv('NEXO_SUPABASE_PUBLISHABLE_KEY','').startswith('sb_publishable_'):
        raise RuntimeError('Falta la clave publicable del proyecto Supabase')
    parsed=make_url(db_url)
    if parsed.drivername!='postgresql+psycopg' or parsed.query.get('sslmode')!='verify-full' or not parsed.query.get('sslrootcert'):
        raise RuntimeError('La nube requiere PostgreSQL con sslmode=verify-full y CA confiable')
    if os.getenv('NEXO_STORAGE_MODE') != 'database':
        raise RuntimeError('La nube requiere almacenamiento durable en PostgreSQL')
    if os.getenv('NEXO_AI_ENABLED', 'false').lower() != 'false':
        raise RuntimeError('IA no habilitada en esta entrega')
    if os.getenv('NEXO_ENV') == 'production' and os.getenv('NEXO_RELEASE_APPROVED') != 'true':
        raise RuntimeError('Falta aceptación documentada del piloto y autorización de gasto')
