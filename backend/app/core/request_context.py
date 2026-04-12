from contextvars import ContextVar, Token
from uuid import uuid4


_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(request_id: str) -> Token[str]:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    _request_id_ctx.reset(token)


def get_request_id() -> str:
    return _request_id_ctx.get("")


def ensure_request_id() -> str:
    request_id = get_request_id()
    if request_id:
        return request_id
    request_id = uuid4().hex
    _request_id_ctx.set(request_id)
    return request_id