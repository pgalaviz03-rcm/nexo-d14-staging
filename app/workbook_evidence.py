"""Bounded OOXML reading and literal, cell-addressed evidence. No recalculation."""
from pathlib import Path,PurePosixPath
from io import BytesIO
import hashlib,json,posixpath,re,zipfile
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

CONTRACT='xlsx-evidence-v1'
MAX_FILE=2*1024*1024;MAX_UNPACKED=20*1024*1024;MAX_CELLS=20000;MAX_TEXT=36000
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

class WorkbookInvalid(ValueError):pass
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def column_number(label):
 n=0
 for c in label:n=n*26+ord(c)-64
 return n
def clean(value):return str(value).replace('\r',' ').replace('\n',' ').replace('\t',' ')

def read_workbook(raw):
 if not raw or len(raw)>MAX_FILE:raise WorkbookInvalid('El Excel debe tener como máximo 2 MB.')
 try:
  with zipfile.ZipFile(BytesIO(raw)) as z:
   entries=z.infolist();names=[e.filename for e in entries]
   if len(names)!=len(set(names)) or len(names)>200 or sum(e.file_size for e in entries)>MAX_UNPACKED:
    raise WorkbookInvalid('El contenido del Excel excede los límites de lectura.')
   for e in entries:
    if e.flag_bits&1 or e.file_size>8*1024*1024 or e.file_size>max(1,e.compress_size)*200:
     raise WorkbookInvalid('El archivo tiene contenido comprimido no admitido.')
    if '\\' in e.filename or e.filename.startswith('/') or '..' in PurePosixPath(e.filename).parts:
     raise WorkbookInvalid('El archivo contiene rutas no admitidas.')
    low=e.filename.lower()
    if any(x in low for x in ('vbaproject','externallinks/','embeddings/','activex/','connections.xml')):
     raise WorkbookInvalid('Usa un XLSX sin macros, objetos ni conexiones externas.')
    if low.endswith('.rels'):
     rels=ET.fromstring(z.read(e),forbid_dtd=True)
     if any(r.get('TargetMode','').lower()=='external' for r in rels):
      raise WorkbookInvalid('Usa una copia sin enlaces externos.')
   def xml(name):return ET.fromstring(z.read(name),forbid_dtd=True)
   wb=xml('xl/workbook.xml');rels={r.get('Id'):r.get('Target') for r in xml('xl/_rels/workbook.xml.rels')}
   strings=[]
   if 'xl/sharedStrings.xml' in names:
    strings=[''.join(n.text or '' for n in si.findall('.//m:t',NS)) for si in xml('xl/sharedStrings.xml').findall('m:si',NS)]
    if len(strings)>MAX_CELLS or any(len(s)>2000 for s in strings):raise WorkbookInvalid('El texto de las celdas excede el límite.')
   sheets=[];count=0
   for s in wb.findall('m:sheets/m:sheet',NS):
    if s.get('state','visible')!='visible':continue
    name=s.get('name','');target=rels.get(s.get(REL),'')
    if not name or len(name)>80 or any(x['name']==name for x in sheets):raise WorkbookInvalid('Revisa los nombres de las hojas.')
    path=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
    if not path.startswith('xl/worksheets/') or '..' in PurePosixPath(path).parts:raise WorkbookInvalid('La hoja no tiene una ruta válida.')
    sheet=xml(path);hidden=set()
    for col in sheet.findall('m:cols/m:col',NS):
     if col.get('hidden') in {'1','true'}:
      lo,hi=int(col.get('min','0')),int(col.get('max','0'))
      if not 1<=lo<=hi<=16384:raise WorkbookInvalid('Columnas no válidas.')
      hidden.update(range(lo,min(hi,80)+1))
    rows={};formula_count=0;missing_formula=0;error_count=0
    for row in sheet.findall('m:sheetData/m:row',NS):
     n=int(row.get('r','0'))
     if not 1<=n<=5000:raise WorkbookInvalid('La lectura admite hasta la fila 5000 por hoja.')
     if row.get('hidden') in {'1','true'}:continue
     if n in rows:raise WorkbookInvalid('Hay filas repetidas.')
     cells={}
     for c in row.findall('m:c',NS):
      count+=1
      if count>MAX_CELLS:raise WorkbookInvalid('La lectura admite hasta 20000 celdas.')
      address=c.get('r','');match=re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})',address)
      if not match or int(match[2])!=n:raise WorkbookInvalid('Hay referencias de celda inválidas.')
      label=match[1];number=column_number(label)
      if number>80:raise WorkbookInvalid('La lectura admite hasta 80 columnas por hoja.')
      if number in hidden:continue
      if label in cells:raise WorkbookInvalid('Hay celdas repetidas.')
      kind=c.get('t','n');v=c.find('m:v',NS);formula=c.find('m:f',NS) is not None
      if formula:formula_count+=1
      if formula and v is None:missing_formula+=1
      if kind=='s':
       idx=int(v.text) if v is not None else -1
       if not 0<=idx<len(strings):raise WorkbookInvalid('Texto compartido no válido.')
       value=strings[idx]
      elif kind=='inlineStr':value=''.join(t.text or '' for t in c.findall('m:is//m:t',NS))
      elif kind=='e':value='[Error de celda]';error_count+=1
      elif kind=='b':value='TRUE' if v is not None and v.text=='1' else 'FALSE'
      else:value=v.text if v is not None and v.text is not None else ''
      if formula and not value:value='[Fórmula sin valor guardado]'
      if len(value)>2000:raise WorkbookInvalid('Una celda excede 2000 caracteres.')
      if value:cells[label]=dict(cell=address,value=value,kind=kind,formula=formula)
     if cells:rows[n]=cells
    sheets.append(dict(name=name,rows=rows,formula_count=formula_count,missing_formula_values=missing_formula,
      cell_errors=error_count,merged_ranges=[e.get('ref') for e in sheet.findall('m:mergeCells/m:mergeCell',NS)]))
    if len(sheets)>8:raise WorkbookInvalid('La lectura admite hasta 8 hojas visibles.')
   if not sheets:raise WorkbookInvalid('No hay hojas visibles para consultar.')
   return sheets
 except WorkbookInvalid:raise
 except (ValueError,KeyError,TypeError,zipfile.BadZipFile,ET.ParseError,DefusedXmlException,OverflowError,RecursionError,RuntimeError,NotImplementedError,OSError):
  raise WorkbookInvalid('No se pudo leer un XLSX válido; revisa su estructura.') from None

def public_structure(sheets):
 return [dict(name=s['name'],rows=len(s['rows']),max_row=max(s['rows'],default=1),columns=[dict(column=k,label=v['value']) for k,v in sorted(s['rows'].get(1,{}).items(),key=lambda kv:column_number(kv[0]))],
   formula_count=s['formula_count'],missing_formula_values=s['missing_formula_values'],cell_errors=s['cell_errors'],merged_ranges=s['merged_ranges']) for s in sheets]

def prepare(raw,filename,selection):
 sheets=read_workbook(raw);sheet=next((s for s in sheets if s['name']==selection.sheet),None)
 if sheet is None:raise WorkbookInvalid('Elige una hoja visible del archivo.')
 columns=sorted(selection.columns,key=column_number)
 if len(set(columns))!=len(columns) or any(column_number(c)>80 for c in columns):raise WorkbookInvalid('Revisa las columnas elegidas.')
 headers=sheet['rows'].get(selection.header_row,{})
 if not headers or any(c not in headers for c in columns):raise WorkbookInvalid('Cada columna elegida necesita un encabezado en la fila indicada.')
 if selection.first_row<=selection.header_row or selection.last_row<selection.first_row:raise WorkbookInvalid('Revisa el intervalo de filas.')
 rows=[(n,{c:cells.get(c) for c in columns}) for n,cells in sorted(sheet['rows'].items()) if selection.first_row<=n<=selection.last_row and any(c in cells for c in columns)]
 if not rows:raise WorkbookInvalid('No hay valores en la selección.')
 sha=hashlib.sha256(raw).hexdigest();name=clean(filename)
 lines=[f'Archivo de origen: {name}',f'SHA256 del original: {sha}',f'Hoja: {clean(sheet["name"])}',
  'Año declarado: '+(str(selection.source_year) if selection.source_year else 'Sin confirmar'),
  'Procedencia declarada: '+(clean(selection.source_note) or 'Aportado por el proyecto; fuente externa sin confirmar'),
  'Lectura literal de valores guardados. Las fórmulas no se recalculan y los números conservan su representación almacenada.',
  'Encabezados: '+'; '.join(c+': '+clean(headers[c]['value']) for c in columns),'']
 records=[]
 for n,cells in rows:
  location=clean(sheet['name'])+'!'+','.join(c+str(n) for c in columns)
  parts=[clean(headers[c]['value'])+f' [{c}{n}]: '+(clean(cells[c]['value']) if cells[c] else '[Sin dato]') for c in columns]
  lines.extend([f'Origen: {name} · {location}','; '.join(parts),''])
  records.append(dict(row=n,location=location,cells=[dict(column=c,label=headers[c]['value'],cell=c+str(n),value=cells[c]['value'] if cells[c] else None) for c in columns]))
 text='\n'.join(lines)
 if len(text)>MAX_TEXT or len(text.encode())>512*1024:raise WorkbookInvalid('La selección es demasiado extensa. Reduce filas o columnas.')
 metadata=dict(contract=CONTRACT,source_sha256=sha,sheet=sheet['name'],columns=columns,header_row=selection.header_row,
  first_row=selection.first_row,last_row=selection.last_row,source_year=selection.source_year,source_note=selection.source_note,row_count=len(rows),text_sha256=hashlib.sha256(text.encode()).hexdigest())
 return dict(metadata=metadata,preview_sha256=digest(metadata),preview=records[:5],records=records,text=text)
