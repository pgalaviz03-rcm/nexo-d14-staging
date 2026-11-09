"""Render ASGI entrypoint; migrations run separately under the schema owner."""
from .main import app as core_app
from .cloud_workspace import install
app=install(core_app)
