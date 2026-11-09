"""Standalone printable evidence document. Escaped text; no scripts or remote assets."""
from html import escape
from urllib.parse import urlsplit

def origin(snapshot):
    return {'local_documentary_briefing_v1':'briefing','explorer_selection_v1':'selection'}.get(snapshot.get('mode'),'documentary')
def render_document(report,*,brand,project):
    esc=lambda value:escape(str(value if value is not None else ''),quote=True)
    s=report['snapshot'];kind=origin(s);label={'briefing':'Briefing','selection':'Selección de evidencias','documentary':'Informe documental'}[kind]
    released=report.get('is_released',report['version']==report.get('published_version'))
    status='Habilitada para lectores del proyecto' if released else 'Borrador de trabajo'
    blocks=[]
    if kind=='briefing':
        cut=s.get('briefing',{});period=cut.get('filters',{})
        blocks.append('<section><h2>Corte de Briefing</h2><p>'+esc(period.get('start'))+' → '+esc(period.get('end'))+'</p></section>')
        value=lambda v:'—' if v is None else esc(v)
        pulse=cut.get('pulse',{});a=cut.get('content_analytics',{})
        summary='<p>Notas: '+value(cut.get('news_count'))+' · Menciones: '+value(pulse.get('metrics',{}).get('mentions'))+' · Señales activadas: '+value(pulse.get('active_alerts'))+'</p>'
        if a:
            summary+='<p>Piezas del corpus: '+value(a.get('pieces'))+' · Con tono clasificado: '+value(a.get('tone_classified'))+' · Índice de tono: '+value(a.get('mood_index'))+'/100 · Burla: '+value(a.get('mockery_percentage'))+' %</p>'
            names={'positive':'Positivo','negative':'Negativo','neutral':'Neutral','joy':'Alegría','anger':'Ira','fear':'Miedo','sadness':'Tristeza','surprise':'Sorpresa'}
            summary+='<ul>'+''.join('<li>'+esc(names.get(r.get('label'),r.get('label','')))+': '+value(r.get('percentage'))+' %</li>' for r in a.get('tone',[]))+'</ul>'
            summary+='<ul>'+''.join('<li>'+esc(names.get(r.get('emotion'),r.get('emotion','')))+': '+value(r.get('percentage'))+' %</li>' for r in a.get('emotions',[]))+'</ul>'
            summary+='<p class="meta">'+esc(a.get('methodology',''))+'</p>'
        if cut.get('topics'):summary+='<h2>Temas consignados en el corte</h2><ul>'+''.join('<li>'+esc(t['name'])+' · '+esc(t['count'])+' notas</li>' for t in cut['topics'])+'</ul>'
        if pulse.get('alerts'):summary+='<h2>Señales conservadas</h2><ul>'+''.join('<li>'+esc(r['name'])+' · '+value(r.get('value'))+' / '+value(r.get('threshold'))+'</li>' for r in pulse['alerts'])+'</ul>'
        blocks.append('<section><h2>Indicadores del corte guardado</h2>'+summary+'</section>')
    if s.get('editorial_note'):blocks.append('<section><h2>Nota del equipo</h2><p class="note">'+esc(s['editorial_note'])+'</p></section>')
    for c in s['context']['citations']:
        stamp=c.get('published_at');basis={'uploaded':'Carga del archivo','ingested':'Ingreso al archivo'}.get(c.get('date_basis'),'Fecha consignada')
        link=''
        try:
            p=urlsplit(c.get('url') or '')
            if p.scheme=='https' and p.hostname and not p.username and not p.password:
                link='<p><a href="'+esc(c['url'])+'" rel="noopener noreferrer">'+esc(c['url'])+'</a></p>'
        except ValueError:pass
        blocks.append('<article><div class="ref">'+esc(c['citation'])+' · '+esc(c['source'])+'</div><h2>'+esc(c['title'])+'</h2>'+
            ('<p class="meta">'+basis+': '+esc(stamp)+'</p>' if stamp else '<p class="meta">Fecha no consignada en la cita.</p>')+
            '<p class="excerpt">'+esc(c.get('excerpt',''))+'</p>'+link+'<p class="hash">Huella de fuente: '+esc(c.get('content_sha256',''))+'</p></article>')
    return '<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+\
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'+\
        '<meta name="referrer" content="no-referrer"><title>'+esc(s['title'])+'</title><style>'+\
        'body{font:15px/1.65 system-ui,sans-serif;background:#f2f5fa;color:#192a46;margin:0}main{max-width:850px;margin:40px auto;background:#fff;padding:48px;box-shadow:0 10px 40px #14233e10}header{border-top:6px solid #7560db;padding-top:24px;border-bottom:1px solid #e3e9f2;padding-bottom:24px}.brand{font-size:13px;font-weight:800;letter-spacing:.12em;color:#7560db}h1{font-size:34px;line-height:1.2;margin:20px 0 14px}h2{font-size:19px;line-height:1.4}.meta,.ref{font-size:12px;color:#63748d}.ref{color:#237967;font-weight:700}section,article{padding:22px 0;border-bottom:1px solid #e7edf4;break-inside:avoid}.excerpt,.note{white-space:pre-wrap;overflow-wrap:anywhere}.hash{font-size:10px;color:#78869b;overflow-wrap:anywhere}a{color:#4e50a0;overflow-wrap:anywhere}footer{margin-top:30px;font-size:12px;color:#63748d}@media print{body{background:white}main{max-width:none;margin:0;padding:0;box-shadow:none}a{color:#192a46}h1{font-size:27px}article{break-inside:auto}h2{break-after:avoid}}@page{size:A4;margin:18mm}'+\
        '</style></head><body><main><header><div class="brand">'+esc(brand)+' · '+esc(project)+'</div><h1>'+esc(s['title'])+'</h1><p class="meta">'+\
        label+' · Versión '+esc(report['version'])+' · '+status+'</p><p class="meta">Guardada: '+esc(report['created_at'])+' · '+str(len(s['context']['citations']))+' fuentes citadas</p></header>'+\
        ''.join(blocks)+'<footer><p>'+esc(s.get('scope',''))+'</p><p>Acceso y distribución: personas autorizadas del proyecto. La copia descargada conserva el estado de esta versión al exportarse.</p>'+\
        '<p class="hash">Huella de versión: '+esc(report['sha256'])+'</p><p>La huella identifica la versión conservada; no certifica la veracidad de sus fuentes.</p></footer></main></body></html>'
