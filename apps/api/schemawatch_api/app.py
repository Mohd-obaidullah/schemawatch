from __future__ import annotations

import asyncio
import logging
import secrets
import threading
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from schemawatch_api import __version__
from schemawatch_api.config import Settings
from schemawatch_api.database import create_db_engine, create_session_factory, init_db
from schemawatch_api.schemas import (
    AcceptResponse,
    AckResponse,
    BaselineResponse,
    ConfigResponse,
    DriftEventResponse,
    EndpointResponse,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    PaginatedResponse,
    StatsResponse,
)
from schemawatch_api.service import SchemawatchService
from schemawatch_api.sse import SSEManager

bearer_scheme = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory for schemawatch FastAPI backend.

    Creates and configures routes, authentication, database connection, and SSE manager.
    Zero global state ensures total isolation across test runs and environments.
    """
    if settings is None:
        settings = Settings()
    settings.validate_token_requirement()

    logger = logging.getLogger("schemawatch.api")
    if settings.dev_mode:
        logger.warning(
            "SECURITY WARNING: SCHEMAWATCH_DEV_MODE is enabled. API authentication is bypassed!"
        )

    # Initialize persistence and engine
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    init_db(engine)

    # Initialize SSE manager and core service
    sse_manager = SSEManager()
    service = SchemawatchService(
        settings=settings,
        session_factory=session_factory,
        sse_manager=sse_manager,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        # Associate running asyncio event loop with service for thread-safe SSE bridge
        loop = asyncio.get_running_loop()
        service.set_loop(loop)
        yield

    app = FastAPI(
        title="schemawatch API",
        description="Open-source API contract drift monitor REST API",
        version=__version__,
        lifespan=lifespan,
        debug=False,
    )

    # Attach service and settings to app state
    app.state.settings = settings
    app.state.service = service
    app.state.engine = engine

    # Security Headers Middleware (CSP, X-Content-Type-Options, Referrer-Policy, X-Frame-Options)
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # Global Exception Handler (prevents leaking internal tracebacks in 500 responses)
    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Internal unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # Configure CORS if allowed origins specified
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Ingest rate limiting state
    ingest_rate_limits: dict[str, list[float]] = {}
    rate_limit_lock = threading.Lock()
    max_ingest_per_minute = 600

    # ---------------------------------------------------------
    # Authentication Dependency
    # ---------------------------------------------------------
    def authenticate(
        request: Request,
        auth: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    ) -> None:
        """Verify API token using constant-time comparison.

        Enforces Authorization: Bearer <token>.
        Tokens are never accepted in query strings or logged.
        """
        if settings.dev_mode and not settings.api_token:
            return

        if (
            not auth
            or not auth.credentials
            or not secrets.compare_digest(auth.credentials, settings.api_token)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: invalid or missing API token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # ---------------------------------------------------------
    # Routes
    # ---------------------------------------------------------
    @app.get(
        "/healthz",
        response_model=HealthResponse,
        summary="Service Health Check",
        operation_id="getHealth",
        tags=["System"],
    )
    def healthz() -> HealthResponse:
        """Public health check endpoint (no authentication required)."""
        return HealthResponse(status="ok", version=__version__)

    @app.get(
        "/api/config",
        response_model=ConfigResponse,
        summary="Get Public System Configuration",
        operation_id="getConfig",
        dependencies=[Depends(authenticate)],
        tags=["Configuration"],
    )
    def get_config() -> ConfigResponse:
        """Get read-only configuration booleans. Never returns tokens, URLs, or secrets."""
        db_type = "postgres" if "postgres" in settings.database_url.lower() else "sqlite"
        return ConfigResponse(
            slack_configured=bool(settings.slack_webhook_url),
            webhook_configured=bool(settings.alert_webhook_url),
            dev_mode=settings.dev_mode,
            min_alert_severity=settings.min_alert_severity,
            learn_samples=settings.learn_samples,
            sample_rate=settings.sample_rate,
            cooldown_seconds=settings.cooldown_seconds,
            database_type=db_type,
        )

    @app.get(
        "/api/stats",
        response_model=StatsResponse,
        summary="Get System and Alert Statistics",
        operation_id="getStats",
        dependencies=[Depends(authenticate)],
        tags=["Statistics"],
    )
    def get_stats() -> StatsResponse:
        """Get aggregate system statistics and hourly drift counts for the last 12 hours."""
        data = service.get_stats()
        return StatsResponse(**data)

    @app.get(
        "/api/endpoints",
        response_model=PaginatedResponse[EndpointResponse],
        summary="List Monitored Endpoints",
        operation_id="listEndpoints",
        dependencies=[Depends(authenticate)],
        tags=["Endpoints"],
    )
    def list_endpoints(
        cursor: int | None = Query(None, description="Cursor for next page"),
        limit: int = Query(50, ge=1, le=100, description="Items per page"),
    ) -> PaginatedResponse[EndpointResponse]:
        """List all monitored third-party API endpoints with health status and alert counts."""
        items, next_cursor, total = service.list_endpoints(cursor=cursor, limit=limit)
        return PaginatedResponse(
            items=[EndpointResponse(**item) for item in items],
            next_cursor=next_cursor,
            total=total,
        )

    @app.get(
        "/api/endpoints/{id}",
        response_model=EndpointResponse,
        summary="Get Endpoint Details",
        operation_id="getEndpoint",
        dependencies=[Depends(authenticate)],
        tags=["Endpoints"],
    )
    def get_endpoint(id: int) -> EndpointResponse:
        """Get detailed metadata for a single endpoint."""
        ep = service.get_endpoint(id)
        if ep is None:
            raise HTTPException(status_code=404, detail=f"Endpoint {id} not found")
        return EndpointResponse(**ep)

    @app.get(
        "/api/endpoints/{id}/baseline",
        response_model=BaselineResponse,
        summary="Get Endpoint Baseline Schema",
        operation_id="getEndpointBaseline",
        dependencies=[Depends(authenticate)],
        tags=["Endpoints"],
    )
    def get_endpoint_baseline(
        id: int,
        version: int | None = Query(None, description="Specific baseline version to retrieve"),
    ) -> BaselineResponse:
        """Retrieve the active or specified baseline schema for an endpoint."""
        b = service.get_baseline(id, version=version)
        if b is None:
            raise HTTPException(status_code=404, detail=f"Baseline not found for endpoint {id}")
        return BaselineResponse(**b)

    @app.post(
        "/api/endpoints/{id}/accept",
        response_model=AcceptResponse,
        summary="Accept Observed Schema as New Baseline",
        operation_id="acceptEndpointBaseline",
        dependencies=[Depends(authenticate)],
        tags=["Endpoints"],
    )
    def accept_endpoint_baseline(id: int) -> AcceptResponse:
        """Adopt latest observed schema as new baseline and acknowledge all open events."""
        res = service.accept_baseline(id)
        if res is None:
            raise HTTPException(status_code=404, detail=f"Endpoint {id} not found")
        new_version, acks_count = res
        return AcceptResponse(
            status="ok",
            endpoint_id=id,
            new_baseline_version=new_version,
            events_acknowledged=acks_count,
        )

    @app.get(
        "/api/events",
        response_model=PaginatedResponse[DriftEventResponse],
        summary="List Drift Events",
        operation_id="listEvents",
        dependencies=[Depends(authenticate)],
        tags=["Events"],
    )
    def list_events(
        severity: str | None = Query(None, description="Severity: breaking, warning, info"),
        vendor: str | None = Query(None, description="Filter by vendor name"),
        endpoint_id: int | None = Query(None, description="Filter by endpoint ID"),
        acknowledged: bool | None = Query(None, description="Filter by acknowledgment"),
        since: datetime | None = Query(None, description="Events detected after timestamp"),
        cursor: int | None = Query(None, description="Cursor for next page"),
        limit: int = Query(50, ge=1, le=100, description="Items per page"),
    ) -> PaginatedResponse[DriftEventResponse]:
        """Query contract drift events with multi-field filtering and pagination."""
        items, next_cursor, total = service.list_events(
            severity=severity,
            vendor=vendor,
            endpoint_id=endpoint_id,
            acknowledged=acknowledged,
            since=since,
            cursor=cursor,
            limit=limit,
        )
        return PaginatedResponse(
            items=[DriftEventResponse(**item) for item in items],
            next_cursor=next_cursor,
            total=total,
        )

    @app.post(
        "/api/events/{id}/ack",
        response_model=AckResponse,
        summary="Acknowledge Drift Event",
        operation_id="acknowledgeEvent",
        dependencies=[Depends(authenticate)],
        tags=["Events"],
    )
    def acknowledge_event(id: int) -> AckResponse:
        """Mark a contract drift event as acknowledged."""
        res = service.set_event_acknowledgment(id, acknowledged=True)
        if res is None:
            raise HTTPException(status_code=404, detail=f"Event {id} not found")
        return AckResponse(status="ok", event_id=id, acknowledged=True)

    @app.post(
        "/api/events/{id}/unack",
        response_model=AckResponse,
        summary="Unacknowledge Drift Event",
        operation_id="unacknowledgeEvent",
        dependencies=[Depends(authenticate)],
        tags=["Events"],
    )
    def unacknowledge_event(id: int) -> AckResponse:
        """Reopen an acknowledged contract drift event."""
        res = service.set_event_acknowledgment(id, acknowledged=False)
        if res is None:
            raise HTTPException(status_code=404, detail=f"Event {id} not found")
        return AckResponse(status="ok", event_id=id, acknowledged=False)

    @app.post(
        "/api/ingest",
        response_model=IngestResponse,
        summary="Ingest Sample Payload",
        operation_id="ingestPayload",
        dependencies=[Depends(authenticate)],
        tags=["Ingest"],
    )
    async def ingest_payload(request: Request) -> IngestResponse:
        """Ingest third-party API response payload for contract drift monitoring.

        Enforces request payload size limits and verifies payload safety.
        """
        # Enforce body size limit
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_ingest_body_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Payload exceeds limit of {settings.max_ingest_body_bytes} bytes",
            )

        body_bytes = await request.body()
        if len(body_bytes) > settings.max_ingest_body_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"Payload exceeds limit of {settings.max_ingest_body_bytes} bytes",
            )

        # Enforce client rate limiting on /api/ingest
        client_host = request.client.host if request.client else "unknown"
        now_ts = time.monotonic()
        with rate_limit_lock:
            history = ingest_rate_limits.setdefault(client_host, [])
            history[:] = [t for t in history if now_ts - t < 60.0]
            if len(history) >= max_ingest_per_minute:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded (max {max_ingest_per_minute}/min)",
                )
            history.append(now_ts)

        try:
            body_json = await request.json()
            ingest_req = IngestRequest(**body_json)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid ingest JSON body: {exc}",
            ) from exc

        # Process payload through watchdog off the main thread
        service.set_loop(asyncio.get_running_loop())
        observed, changes, event_ids = await asyncio.to_thread(
            service.ingest_payload,
            ingest_req.vendor,
            ingest_req.endpoint,
            ingest_req.payload,
        )

        return IngestResponse(
            status="ok",
            observed=observed,
            changes_detected=len(changes),
            event_ids=event_ids,
        )

    @app.get(
        "/api/events/stream",
        summary="Real-time Server-Sent Events Stream",
        operation_id="streamEvents",
        dependencies=[Depends(authenticate)],
        tags=["Events"],
    )
    async def stream_events() -> StreamingResponse:
        """Subscribe to real-time contract drift alerts via SSE.

        Emits 'event: drift' on new changes, with keep-alive pings every 15s.
        """
        service.set_loop(asyncio.get_running_loop())
        return StreamingResponse(
            sse_manager.subscribe(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ---------------------------------------------------------
    # Frontend Static Files Mount & SPA Fallback (Production)
    # ---------------------------------------------------------
    frontend_dist = Path(__file__).resolve().parent.parent.parent / "web" / "dist"
    if frontend_dist.is_dir():

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_frontend_spa(full_path: str) -> Response:
            # If path points to an existing file in dist, serve it
            target = frontend_dist / full_path
            if full_path and target.is_file():
                return FileResponse(target)
            # Otherwise return index.html for SPA client-side routing
            index_path = frontend_dist / "index.html"
            if index_path.is_file():
                return FileResponse(index_path)
            return Response("Frontend build index.html not found", status_code=404)

    return app
