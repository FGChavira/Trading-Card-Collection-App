"""
Trading Card Collection - HTTP API.

A thin FastAPI layer over the shared read functions in db.py. The CLI and this API call
the same database functions and share one connection pool.

Run locally:
    uvicorn web_api:app --reload

Then open http://127.0.0.1:8000/docs for interactive documentation.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import db

app = FastAPI(
    title="Trading Card Collectoin API",
    description="Search and look up cards in a personal trading card collection.",
    version="0.1.0",
)

# Tell the browser which origins are allowed to call this API from JS.
app.add_middleware(
    CORSMiddleware,
    # For now, "*" allows any origin.
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Liveness check - confirms the service and its DBpool are reachable."""
    try:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return {"status": "ok"}
    except Exception as exc: # surfaced as 503 so uptime checks can see
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")


@app.get("/cards")
def list_cards(
    search: str = Query("", description="Partial or full card name to search for."),
    limit: int = Query(50, ge=1, le=200, description="Max results to return."),
    offset: int = Query(0, ge=0, description="Results to skip (pagination).")
):
    """
    Search across TCG, sports, and collector cards by name.
    An empty search returns the first page of the whole collection.
    """
    results = db.search_cards(search, limit=limit, offset=offset)
    return {
        "search": search,
        "limit": limit,
        "offset": offset,
        "results": results,
    }


@app.get("/cards/{source}/{category}/{set_name}/{id_in_set}")
def read_card(source: str, category: str, set_name: str, id_in_set: str):
    """
    Fetch a single card.
    
    Args:
        source: One of 'tcg', 'sports', or 'collector'.
        category: Category (tcg/collector) or sport (sports), e.g. 'Pokemon'.
        id_in_set: Card number within its set.
    """
    try:
        card = db.get_card(source, category, set_name, id_in_set)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card