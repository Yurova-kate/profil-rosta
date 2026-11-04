"""Application entrypoint: original MVP and competency module."""
from .main import app
from . import competencies, development

app.include_router(competencies.router)
app.include_router(development.router)

@app.on_event("startup")
def initialize_competency_tables():
    competencies.initialize()
    development.initialize()
