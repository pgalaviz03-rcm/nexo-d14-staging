"""Reviewed public Actor references. Configuration only; never runs an Actor."""
from pydantic import Field, model_validator
from .apify_port import Strict

NETWORKS = {'facebook': 'Facebook', 'instagram': 'Instagram', 'tiktok': 'TikTok', 'x': 'X', 'youtube': 'YouTube'}

def entry(network, purpose, label, actor, mode='', transport='batch'):
    return dict(key=network+'.'+purpose, network=network, label=label, actor_ref=actor,
                mode=mode, transport=transport, url='https://apify.com/'+actor)

PROCESSES = [
    entry('facebook','posts','Publicaciones','apify/facebook-posts-scraper'),
    entry('facebook','comments','Comentarios','apify/facebook-comments-scraper'),
    entry('facebook','profile','Estadísticas de cuenta','apify/facebook-pages-scraper'),
    entry('facebook','reactions','Reacciones identificables','scraper_one/facebook-reactions-scraper'),
    entry('instagram','posts','Publicaciones y reels','apify/instagram-scraper','posts'),
    entry('instagram','comments','Comentarios','apify/instagram-scraper','comments'),
    entry('instagram','profile','Estadísticas de cuenta','apify/instagram-scraper','details'),
    entry('tiktok','posts','Videos','clockworks/tiktok-scraper'),
    entry('tiktok','comments','Comentarios','clockworks/tiktok-comments-scraper'),
    entry('tiktok','profile','Estadísticas de cuenta','clockworks/tiktok-profile-scraper'),
    entry('x','posts','Publicaciones y búsquedas','apidojo/tweet-scraper'),
    entry('x','comments','Respuestas','apidojo/x-api','replies','standby'),
    entry('x','profile','Estadísticas de cuenta','apidojo/x-api','profile','standby'),
    entry('youtube','posts','Videos','streamers/youtube-scraper'),
    entry('youtube','comments','Comentarios','streamers/youtube-comments-scraper'),
    entry('youtube','profile','Estadísticas del canal','streamers/youtube-channel-scraper'),
]
BY_KEY = {p['key']: p for p in PROCESSES}

class ApifyProcessInput(Strict):
    selected: bool = False
    actor_ref: str = Field(max_length=160)
    task_ref: str = Field(default='', max_length=100, pattern=r'^[A-Za-z0-9_-]*$')
    dataset_ref: str = Field(default='', max_length=100, pattern=r'^[A-Za-z0-9_-]*$')
    max_items: int = Field(default=20, ge=1, le=500, strict=True)
    daily_limit: int = Field(default=1, ge=0, le=2, strict=True)

def validate_processes(processes):
    for key, process in (processes or {}).items():
        definition = BY_KEY.get(key)
        if not definition or process.actor_ref != definition['actor_ref']:
            raise ValueError('El proceso no corresponde a esta red y función.')
        if definition['transport'] == 'standby' and (process.task_ref or process.dataset_ref):
            raise ValueError('El proceso de X en modo API no utiliza tareas ni datasets.')
    return processes

def catalog():
    return dict(reviewed_on='2026-11-10', networks=NETWORKS, processes=PROCESSES,
                schedule=dict(time='08:00', timezone='America/Mexico_City'), runtime_enabled=False)
