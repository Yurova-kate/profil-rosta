"""Application entrypoint: original MVP and competency module."""
from .main import app
from . import competencies

app.include_router(competencies.router)

@app.on_event("startup")
def initialize_competency_tables():
    competencies.initialize()
