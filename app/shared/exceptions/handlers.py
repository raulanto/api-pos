"""Exception handlers globales: TODO error sale con el sobre `ErrorResponse`.

`{ "success": false, "error": { "code", "message", "fields"? } }`

Los routers/casos de uso siguen lanzando `HTTPException` (directamente o vía sus
helpers `_traducir`); acá se les da forma uniforme. No hay que tocar cada módulo.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.responses.envelope import ErrorDetail, ErrorResponse

logger = logging.getLogger("app.errors")

_STATUS_CODE: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_409_CONFLICT: "CONFLICT",
    422: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "RATE_LIMITED",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
}


def _code_for_status(code: int) -> str:
    return _STATUS_CODE.get(code, f"HTTP_{code}")


def _envelope(status_code: int, code: str, message: str, *, fields=None, headers=None) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, fields=fields))
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(exclude_none=True),
        headers=headers,
    )


def _group_validation_errors(errors: list[dict]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for err in errors:
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        key = ".".join(loc) or "__root__"
        grouped.setdefault(key, []).append(err.get("msg", "inválido"))
    return grouped


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError):
        return _envelope(
            422,
            "VALIDATION_ERROR",
            "Los datos enviados no son válidos",
            fields=_group_validation_errors(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        message = detail if isinstance(detail, str) else _code_for_status(exc.status_code)
        return _envelope(
            exc.status_code,
            _code_for_status(exc.status_code),
            message,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception):
        logger.exception("Error no controlado en %s %s", request.method, request.url.path)
        return _envelope(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "Ocurrió un error interno. Intentá de nuevo más tarde.",
        )
