"""Application entrypoint: original MVP and competency module."""
from .main import app
from . import competencies, development, career

app.include_router(competencies.router)
app.include_router(development.router)
app.include_router(career.router)

@app.on_event("startup")
def initialize_competency_tables():
    competencies.initialize()
    development.initialize()
    career.initialize()

from fastapi.responses import FileResponse
from pathlib import Path

@app.get("/development.js",include_in_schema=False)
def development_script():
    return FileResponse(Path(__file__).resolve().parents[1]/"web"/"development.js",media_type="application/javascript")
