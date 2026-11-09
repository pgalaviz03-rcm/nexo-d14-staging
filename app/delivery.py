"""Offline scheduling, frozen message rendering and fail-closed provider port."""
from datetime import datetime,timedelta,timezone,time
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
import base64,hashlib,os,re
from cryptography.fernet import Fernet,InvalidToken
from fastapi import HTTPException

UTC=timezone.utc
EMOTIONS={'joy':'Alegría','anger':'Ira','surprise':'Sorpresa','fear':'Miedo','sadness':'Tristeza'}
def next_occurrence(schedule,after):
    if after.tzinfo is None:raise ValueError('Se requiere fecha con zona horaria.')
    try:zone=ZoneInfo(schedule.timezone)
    except (ZoneInfoNotFoundError,ValueError):raise ValueError('Zona horaria IANA no válida.') from None
    hour,minute=map(int,schedule.local_time.split(':'));local=after.astimezone(zone)
    for offset in range(15):
        day=local.date()+timedelta(days=offset)
        if schedule.frequency=='weekdays' and day.weekday()>4:continue
        if schedule.frequency=='weekly' and day.weekday()!=schedule.weekday:continue
        candidate=datetime.combine(day,time(hour,minute),zone).replace(fold=0)
        stamp=candidate.astimezone(UTC)
        if stamp.astimezone(zone).replace(tzinfo=None)!=candidate.replace(tzinfo=None):continue
        if stamp>after.astimezone(UTC):return stamp
    raise ValueError('No se encontró un horario válido.')

def cipher():
    explicit=os.getenv('NEXO_DELIVERY_ENCRYPTION_KEY')
    if explicit:
        try:return Fernet(explicit.encode('ascii'))
        except (ValueError,UnicodeError):raise HTTPException(409,'La clave de cifrado de destinos necesita revisión.') from None
    if os.getenv('NEXO_ENV','local')!='local':raise HTTPException(409,'Falta la clave independiente de cifrado de destinos.')
    secret=os.getenv('NEXO_SECRET_KEY','')
    if len(secret)<32:raise HTTPException(409,'Falta la clave privada local para cifrar destinos.')
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('nexo.delivery.v1\0'+secret).encode()).digest()))

def seal(value):return cipher().encrypt(value.encode()).decode()
def unseal(value):
    try:return cipher().decrypt(value.encode()).decode()
    except (InvalidToken,UnicodeError):raise HTTPException(409,'El destino necesita configurarse de nuevo tras un cambio de clave.') from None

def validate_destination(channel,value):
    value=value.strip()
    if channel=='email' and re.fullmatch(r'[^@\s<>\r\n]+@[^@\s<>\r\n]+\.[^@\s<>\r\n]+',value):return value
    if channel=='telegram' and re.fullmatch(r'-?[1-9][0-9]{2,19}',value):return value
    raise HTTPException(422,'Escribe un correo válido o un ID numérico de chat privado de Telegram.')

def mask(channel,value):return (value[:1]+'***@'+value.rsplit('@',1)[1]) if channel=='email' else '***'+value[-4:]

class DeliveryUnavailable(RuntimeError):pass
class DisabledSender:
    def send(self,*,destination,text,idempotency_key):
        raise DeliveryUnavailable('Envíos externos desactivados. No se realiza ninguna llamada ni cargo.')

def message_text(brief,brand='NEXO'):
    fmt=lambda n:'Sin dato' if n is None else f'{n:g}' if isinstance(n,(float,int)) else str(n)
    a=brief.get('content_analytics')
    lines=[f'{brand} · Briefing · {brief["project_name"]}',f'Periodo: {brief["filters"]["start"]} → {brief["filters"]["end"]}']
    if a:
        lines += [f'Piezas observadas únicas por URL: {a["pieces"]}. Tono clasificado: {a["tone_classified"]}.',f'Ánimo del contenido: {a["mood"]} · índice {fmt(a["mood_index"])} /100.']
        for row in a['tone']:lines.append({'positive':'Positivo','negative':'Negativo','neutral':'Neutral'}[row['label']]+': '+fmt(row['percentage'])+' %')
        lines.append(f'Burla: {fmt(a["mockery_percentage"])} % · {a["mockery_classified"]} piezas codificadas.')
        lines.append('Emociones: '+', '.join(EMOTIONS[r['emotion']]+': '+fmt(r['percentage'])+' %' for r in a['emotions'])+f'. Base: {a["emotion_classified"]}.')
        lines.append('Porcentajes entre piezas clasificadas en cada dimensión; burla puede coexistir con tono y emoción.')
    else:lines.append('Este corte se guardó antes del desglose de emociones y burla. Esas métricas no están disponibles; prepara otro corte para incorporarlas.')
    lines.append('Temas del periodo: '+(', '.join(t['name'][:60]+f' ({t["count"]})' for t in brief['topics'][:3]) or 'Sin temas asignados.'))
    pulse=brief['pulse'];lines.append('Alertas activadas: '+fmt(pulse['active_alerts'])+f' · {pulse["alerts_evaluated"]} reglas evaluables.')
    for alert in pulse['alerts'][:3]:lines.append('Señal para revisar: '+alert['name'][:100]+f' · {fmt(alert["value"])} / umbral {alert["threshold"]}.')
    lines.append(f'Pendientes: {brief["review_status"]["needs_check"]} notas requieren comprobación; {brief["review_status"]["unreviewed"]} sin revisar.')
    lines.append('Fuentes seleccionadas: '+(', '.join('['+c['citation']+'] '+c['title'][:90] for c in brief['citations'][:2]) or 'Sin fuentes en el corte.'))
    lines.append('Tono de contenido observado; no encuesta ni predicción de riesgo. Consulta fuentes y cobertura completa en NEXO.')
    text='\n'.join(lines)
    # Conservative plain-text envelope for Telegram and future email adapters.
    while len(text.encode('utf-16-le'))//2>3500:text=text[:-40]
    return text
