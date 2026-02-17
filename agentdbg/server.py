"""
Minimal FastAPI server for the local viewer (SPEC §10).

Serves GET /api/runs, GET /api/runs/{run_id}, GET /api/runs/{run_id}/events,
and GET / with static index.html. No CORS by default.
"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import agentdbg.storage as storage
from agentdbg.config import load_config

SPEC_VERSION = "0.1"
UI_INDEX_PATH = Path(__file__).resolve().parent / "ui_static" / "index.html"


def create_app() -> FastAPI:
    """Create and return the FastAPI application for the local viewer."""
    app = FastAPI(title="AgentDbg Viewer")

    @app.get("/api/runs")
    def get_runs() -> dict:
        """List recent runs. Response: { spec_version, runs }."""
        config = load_config()
        runs = storage.list_runs(limit=50, config=config)
        return {"spec_version": SPEC_VERSION, "runs": runs}

    @app.get("/api/runs/{run_id}")
    def get_run_meta(run_id: str) -> dict:
        """Return run.json metadata for the given run_id."""
        config = load_config()
        try:
            return storage.load_run_meta(run_id, config)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid run_id")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")

    @app.get("/api/runs/{run_id}/events")
    def get_run_events(run_id: str) -> dict:
        """Return events array for the run. 404 if run not found."""
        config = load_config()
        try:
            storage.load_run_meta(run_id, config)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid run_id")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="run not found")
        try:
            events = storage.load_events(run_id, config)
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid run_id")
        return {
            "spec_version": SPEC_VERSION,
            "run_id": run_id,
            "events": events,
        }

    @app.get("/")
    def serve_ui() -> FileResponse:
        """Serve the static HTML UI with content-type text/html."""
        if not UI_INDEX_PATH.is_file():
            raise HTTPException(
                status_code=404,
                detail="UI not found: agentdbg/ui_static/index.html is missing",
            )
        return FileResponse(
            UI_INDEX_PATH,
            media_type="text/html",
        )

    return app
