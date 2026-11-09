"""Bounded offline PDF text extraction in an isolated, resource-limited process.

PDF text is untrusted evidence, never instructions. No OCR, rendering, URLs,
attachments or scripts are executed. The caller retains the immutable original.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CONTRACT = 'pdf-evidence-v1'
MAX_FILE = 12 * 1024 * 1024
MAX_PAGES = 160
MAX_TEXT = 300_000
MAX_PACKET = 500 * 1024
TIMEOUT = 25

class PdfInvalid(ValueError):
    pass

def _windows_job(process):
    """Kill the child on close and bound committed child memory to 512 MiB."""
    import ctypes as c
    from ctypes import wintypes as w
    class Basic(c.Structure):
        _fields_=[('process_time',c.c_int64),('job_time',c.c_int64),('flags',w.DWORD),
                  ('min_working',c.c_size_t),('max_working',c.c_size_t),('active',w.DWORD),
                  ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class IO(c.Structure):
        _fields_=[(n,c.c_uint64) for n in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
    class Extended(c.Structure):
        _fields_=[('basic',Basic),('io',IO),('process_memory',c.c_size_t),('job_memory',c.c_size_t),
                  ('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
    kernel=c.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[c.c_void_p,w.LPCWSTR];kernel.CreateJobObjectW.restype=w.HANDLE
    kernel.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
    kernel.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
    kernel.CloseHandle.argtypes=[w.HANDLE]
    handle=kernel.CreateJobObjectW(None,None)
    if not handle:raise OSError('job creation failed')
    limits=Extended();limits.basic.flags=0x2000|0x100;limits.process_memory=512*1024*1024
    if not kernel.SetInformationJobObject(handle,9,c.byref(limits),c.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle,w.HANDLE(int(process._handle))):
        kernel.CloseHandle(handle);raise OSError('job limit failed')
    return lambda:kernel.CloseHandle(handle)

def extract_pdf(raw,work_directory=None):
    if not raw.startswith(b'%PDF-') or len(raw)>MAX_FILE:
        raise PdfInvalid('Elige un PDF válido de hasta 12 MB.')
    # Private temporary files; stripped environment cannot carry provider secrets.
    env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP','LANG'}}
    temporary=Path(work_directory) if work_directory else Path.cwd()/'work/private/pdf-temporary'
    temporary.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='nexo-pdf-',dir=temporary) as directory:
        source=Path(directory)/'source.pdf';result=Path(directory)/'text.json'
        source.write_bytes(raw)
        child=subprocess.Popen([sys.executable,'-I',str(Path(__file__).resolve()),'--worker',str(source),str(result)],
            stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        close_job=lambda:None
        try:
            if os.name=='nt':close_job=_windows_job(child)
            # The child does not parse anything until resource limits are set.
            child.communicate(input=b'go',timeout=TIMEOUT)
            if child.returncode or not result.exists() or result.stat().st_size>MAX_PACKET:
                raise PdfInvalid('No se pudo leer este PDF. Revisa que no esté dañado o protegido con contraseña.')
            packet=json.loads(result.read_text(encoding='utf-8'))
        except subprocess.TimeoutExpired:
            raise PdfInvalid('El PDF tardó demasiado en procesarse. Prueba una copia más pequeña.') from None
        except (OSError,ValueError) as exc:
            if isinstance(exc,PdfInvalid):raise
            raise PdfInvalid('No se pudo preparar el PDF de forma segura.') from None
        finally:
            if child.poll() is None:child.kill()
            child.wait(timeout=5);close_job()
    if packet.get('error'):raise PdfInvalid(packet['error'])
    return packet

def _worker(source,output):
    if sys.stdin.buffer.read(2)!=b'go':return
    if os.name!='nt':
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(20,20))
    from pypdf import PdfReader,overwrite_configuration,__version__
    # Public pypdf configuration API, scoped to this isolated worker.
    limit=8*1024*1024
    overwrite_configuration(maximum_declared_stream_length=limit,
        array_based_stream_maximum_output_length=limit,lzw_maximum_output_length=limit,
        run_length_maximum_output_length=limit,zlib_maximum_output_length=limit,
        jbig2_maximum_output_length=limit,brotli_maximum_output_length=limit,
        image_maximum_buffer_size=limit,stream_decoding_work_maximum_length=3*limit,
        disable_legacy_handling=True)
    raw=Path(source).read_bytes()
    reader=PdfReader(io.BytesIO(raw),strict=True)
    if reader.is_encrypted:raise PdfInvalid('El PDF está protegido con contraseña. Sube una copia autorizada sin protección.')
    count=len(reader.pages)
    if not count or count>MAX_PAGES:raise PdfInvalid('La lectura local admite PDF de 1 a 160 páginas. Divide este documento.')
    pages=[];empty=[];total=0
    for index,page in enumerate(reader.pages,1):
        text=(page.extract_text() or '').replace('\x00','').strip()
        text=''.join(c for c in text if c in '\n\t' or ord(c)>=32)
        total+=len(text)
        if total>MAX_TEXT:raise PdfInvalid('El PDF contiene demasiado texto para una sola lectura. Divídelo en partes.')
        if not text:empty.append(index)
        pages.append(dict(number=index,text=text))
    packet=dict(contract=CONTRACT,page_count=count,pages=pages,empty_pages=empty,
                text_chars=total,extractor='pypdf-'+__version__,ocr_used=False)
    encoded=json.dumps(packet,ensure_ascii=False,sort_keys=True).encode('utf-8')
    if len(encoded)>MAX_PACKET:raise PdfInvalid('El texto del PDF supera el límite local. Divide el documento.')
    Path(output).write_bytes(encoded)

if __name__=='__main__':
    try:_worker(sys.argv[2],sys.argv[3])
    except PdfInvalid as exc:Path(sys.argv[3]).write_text(json.dumps(dict(error=str(exc))),encoding='utf-8')
    except Exception:raise SystemExit(1)
