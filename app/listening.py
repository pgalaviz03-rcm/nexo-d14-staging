"""RSS ingestion; no AI/semantic classification. Network URLs require project-admin allowlist.

A feed never becomes representative polling data. Provider failures preserve historical data.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import hashlib, html, ipaddress, os, re, socket, ssl, http.client, time
import dns.resolver
import httpx
from defusedxml import ElementTree

MAX_FEED_BYTES = 2_000_000
MAX_ITEMS = 80
MAX_DESCRIPTION = 360


def normalize_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 1500:
        raise ValueError('URL demasiado larga')
    p = urlparse(url.strip())
    if any(ord(c)<33 or ord(c)==127 for c in url) or '\\' in url:
        raise ValueError('URL contiene caracteres inválidos')
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Solo HTTPS estándar sin credenciales')
    if p.hostname.endswith('.') or '%' in p.netloc or '\\' in p.netloc:
        raise ValueError('Host inválido')
    try:
        host = p.hostname.encode('idna').decode('ascii').lower()
    except UnicodeError as e:
        raise ValueError('Host inválido') from e
    if host == 'localhost' or host.endswith('.local') or host.endswith('.internal'):
        raise ValueError('Host local prohibido')
    try:
        ipaddress.ip_address(host)
        raise ValueError('IP literal prohibida')
    except ValueError as e:
        if str(e) == 'IP literal prohibida': raise
    query = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True) if not k.lower().startswith('utm_')]
    return urlunparse(('https',host,p.path or '/', '', urlencode(query),''))


def validate_feed_url(url: str) -> str:
    normalized=normalize_url(url)
    host=urlparse(normalized).hostname
    allowed={h.strip().lower() for h in os.getenv('NEXO_RSS_ALLOWED_HOSTS','').split(',') if h.strip()}
    if not allowed or host not in allowed:
        raise ValueError('El dominio no está en NEXO_RSS_ALLOWED_HOSTS')
    return normalized


def resolve_public(host: str):
    """Bounded DNS lookup. Return validated numeric addresses, never resolve twice."""
    resolver=dns.resolver.Resolver()
    resolver.timeout=1
    resolver.lifetime=2
    addresses=[]
    for kind in ('A','AAAA'):
        try:
            addresses.extend(str(a) for a in resolver.resolve(host,kind,lifetime=2))
        except dns.resolver.NoAnswer:
            pass
        except dns.exception.DNSException as exc:
            raise ValueError('No fue posible validar DNS') from exc
    if not addresses:raise ValueError('DNS sin direcciones')
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if not ip.is_global or getattr(ip,'ipv4_mapped',None) or getattr(ip,'sixtofour',None) or getattr(ip,'teredo',None):
            raise ValueError('DNS resolvió a una dirección no pública o de transición')
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,address):
        super().__init__(host,443,timeout=4,context=ssl.create_default_context())
        self.address=address

    def connect(self):
        # Connect to the validated IP. Hostname is used only for SNI/certificate
        # verification. No proxies, redirects, second DNS lookup or TLS bypass.
        ipaddress.ip_address(self.address)
        sock=socket.create_connection((self.address,443),timeout=4)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def safe_text(text:str | None,limit:int)->str:
    return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]*>',' ',text or ''))).strip()[:limit]


def child_text(item, *names)->str:
    for c in item:
        tag=c.tag.rsplit('}',1)[-1]
        if tag in names:
            return ''.join(c.itertext()).strip() if tag!='link' else (c.attrib.get('href') or (c.text or '')).strip()
    return ''


def parse_date(s):
    if not s:return None
    from email.utils import parsedate_to_datetime
    try:
        d=parsedate_to_datetime(s)
        if d:return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):pass
    try:
        d=datetime.fromisoformat(s.replace('Z','+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:return None


def parse_feed(raw:bytes):
    if len(raw)>MAX_FEED_BYTES:raise ValueError('RSS sobrepasa 2 MB')
    try:root=ElementTree.fromstring(raw)
    except Exception as e:raise ValueError('XML de fuente RSS/Atom inválido') from e
    tag=root.tag.rsplit('}',1)[-1].lower()
    if tag not in ('rss','feed','rdf'):raise ValueError('No es un documento RSS o Atom')
    items=[c for c in root.iter() if c.tag.rsplit('}',1)[-1] in ('item','entry')][:MAX_ITEMS]
    parsed=[]
    for i in items:
        title=safe_text(child_text(i,'title'),650)
        url=child_text(i,'link')
        if not url:
            url=child_text(i,'guid','id')
        try:url=normalize_url(url)
        except ValueError:continue
        if not title:continue
        abstract=safe_text(child_text(i,'description','summary','content','encoded'),MAX_DESCRIPTION)
        published=parse_date(child_text(i,'pubDate','published','updated','date'))
        parsed.append(dict(title=title,url=url,abstract=abstract,published_at=published))
    return parsed


def fetch_rss(url: str) -> bytes:
    if os.getenv('NEXO_OFFLINE')=='true':
        raise ValueError('Conexiones externas desactivadas en modo local')
    safe=validate_feed_url(url)
    p=urlparse(safe)
    addresses=resolve_public(p.hostname)
    conn=PinnedHTTPS(p.hostname,addresses[0])
    deadline=time.monotonic()+12
    try:
        conn.request('GET',p.path+('?' + p.query if p.query else ''),headers={
            'User-Agent':'NEXO-Observatorio/0.5','Accept-Encoding':'identity','Connection':'close'})
        r=conn.getresponse()
        if r.status != 200:raise ValueError(f'La fuente devolvió HTTP {r.status}')
        if r.getheader('Content-Encoding','identity').lower() not in ('identity',''):
            raise ValueError('Compresión de RSS no permitida')
        typ=r.getheader('Content-Type','').lower()
        if not any(x in typ for x in ('xml','rss','atom','text/plain')):
            raise ValueError('Tipo de contenido no permitido')
        if int(r.getheader('Content-Length','0'))>MAX_FEED_BYTES:
            raise ValueError('RSS excede 2 MB')
        parts=[];used=0
        while True:
            if time.monotonic()>deadline:raise ValueError('Tiempo RSS agotado')
            chunk=r.read1(65536)
            if not chunk:break
            used+=len(chunk)
            if used>MAX_FEED_BYTES:raise ValueError('RSS excede 2 MB')
            parts.append(chunk)
        return b''.join(parts)
    finally:
        conn.close()


def digest_url(url:str)->str:
    return hashlib.sha256(url.encode('utf-8')).hexdigest()
