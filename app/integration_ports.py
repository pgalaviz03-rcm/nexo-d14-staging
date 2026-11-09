"""Provider-independent contracts. No SDK, network request or secret lookup."""
from typing import Protocol


class GenerationUnavailable(RuntimeError):
    pass


class GenerationPort(Protocol):
    def answer(self, context_packet: dict) -> dict: ...


class DisabledGeneration:
    def answer(self, context_packet: dict) -> dict:
        raise GenerationUnavailable('Generación desactivada; solo se prepara evidencia local con citas.')


class LocalDocumentarySummary:
    """Extractive dossier only: no inference, SDK, model, cache or network I/O.

    Packets must come from the authorized, project-scoped retrieval route.
    Source excerpts remain untrusted quotations, never operational instructions.
    """

    def answer(self, context_packet: dict) -> dict:
        citations = context_packet['citations']
        return dict(
            mode='local_documentary_digest',
            project_id=context_packet['project_id'],
            question=context_packet['question'],
            status='fragments_found' if citations else 'no_matches',
            answer=None,
            ai_used=False,
            external_calls=0,
            from_cache=False,
            citations=citations,
            coverage=context_packet['coverage'],
            note=('Ficha de extractos para revisión humana; las coincidencias no verifican hechos.'
                  if citations else
                  'No hay coincidencias en el archivo consultado; no se genera una respuesta.'),
        )


def connection_catalog():
    # Readiness describes the interface, never a connection or provider test.
    return [
        dict(id='database', name='Datos del proyecto', state='local', provider='SQLite',
             next_step='Ensayar migraciones y RLS en PostgreSQL antes de publicar.'),
        dict(id='retrieval', name='Búsqueda de evidencia', state='local', provider='Búsqueda léxica',
             next_step='Evaluar recuperación semántica con una muestra revisada.'),
        dict(id='generation', name='Modelo de lenguaje', state='disabled', provider=None,
             next_step='Elegir proveedor, presupuesto, política de datos y evaluación.'),
        dict(id='embeddings', name='Embeddings e índice vectorial', state='disabled', provider=None,
             next_step='Definir modelo y versiones; probar aislamiento y calidad del índice.'),
        dict(id='rss', name='Lectura RSS externa', state='disabled', provider=None,
             next_step='Activar únicamente dominios autorizados y cuota explícita.'),
        dict(id='social', name='APIs de contenido público', state='disabled', provider=None,
             next_step='Conectar una fuente autorizada por vez y verificar sus campos.'),
        dict(id='delivery', name='Entrega de reportes', state='disabled', provider=None,
             next_step='Autorizar canales y destinatarios antes de cualquier envío.'),
    ]
