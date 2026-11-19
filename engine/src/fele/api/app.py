"""FastAPI app. Serves aggregates and model outputs only — never raw GRID events.

Interactive docs are generated from the code: Swagger UI at /docs, ReDoc at /redoc, spec at /openapi.json.
"""

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from fele import prefs

DESCRIPTION = """
**fele** (short for *Fearless Ledger*) — draft prep and Fearless series planning for League of Legends coaches.

Every statistic carries its sample size; recommendations are ranked options with reasons, never orders.
Only aggregates are served — raw GRID match data never leaves the local machine.
"""

app = FastAPI(
    title="fele API",
    version="0.1.0",
    description=DESCRIPTION,
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "system", "description": "Health and service metadata."},
        {"name": "coach", "description": "Coach and player preferences (comfort picks, prio players, save lists)."},
    ],
)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


class Health(BaseModel):
    status: Literal["ok"]
    service: str


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")


@app.get("/health", tags=["system"], summary="Liveness check")
def health() -> Health:
    return Health(status="ok", service="fele")


@app.get("/preferences", tags=["coach"], summary="Current coach preferences")
def preferences() -> prefs.Preferences:
    """Coach input from `config/preferences.yaml`, falling back to the example file."""
    return prefs.load()
