import logging
import time
import uuid

from fastapi import FastAPI, Request
from app.api.routes import router

app = FastAPI(title="ContentOps API")

logger = logging.getLogger("contentops.api")


@app.middleware("http")
async def request_observability(request: Request, call_next):
    """Adds traceability without logging headers, bodies, or secrets."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response

app.include_router(router)
