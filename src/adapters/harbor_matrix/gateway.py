import asyncio
import hmac
import json
import logging
from http import HTTPStatus
from types import TracebackType

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from adapters.harness.openrouter_client import MODEL_PROVIDERS

LOGGER = logging.getLogger(__name__)
GATEWAY_VERSION = "2"
MAX_HEADER_BYTES = 64 * 1024
MAX_BODY_BYTES = 16 * 1024 * 1024
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
# The sign-off set: a task ships only if both of these clear the bar. The
# earlier trio (Luna, GLM, DeepSeek) is retired -- every score they produced
# predates the timezone fixes and none of it may be carried forward.
MODEL_ALIASES: dict[str, str] = {
    "opus-5": "anthropic/claude-opus-5",
    "gpt-5.6-sol": "openai/gpt-5.6-sol",
}
# Routable, but not part of the sign-off set, and kept in a separate dict
# because ``len(MODEL_ALIASES)`` is what sizes a Hartwell matrix batch --
# adding a diagnostic model there would silently change that suite's cost.
#
# Codex normalises a slashed model id to its last segment before the request
# reaches this gateway, so ``z-ai/glm-5.2`` arrives as ``glm-5.2`` and
# resolves to "unsupported model" with no pins. These entries put the family
# back on.
DIAGNOSTIC_ALIASES: dict[str, str] = {
    "kimi-k3": "moonshotai/kimi-k3",
    "glm-5.2": "z-ai/glm-5.2",
    "deepseek-v4-flash-0731": "deepseek/deepseek-v4-flash-0731",
}


# Codex speaks the Responses API; opencode's openai provider speaks Chat
# Completions. Both accept the same `model` and `provider` fields, so one
# gateway pins and forwards either -- routed by the inbound path to the
# matching OpenRouter endpoint.
_UPSTREAM_SUFFIX = {
    "/v1/responses": "/responses",
    "/v1/chat/completions": "/chat/completions",
}


class GatewayConfig(BaseModel):
    openrouter_api_key: SecretStr
    gateway_token: SecretStr
    bind_host: str = Field(min_length=1)
    port: int = Field(default=0, ge=0, le=65535)
    upstream_url: str = "https://openrouter.ai/api/v1/responses"

    @property
    def upstream_base(self) -> str:
        # Everything up to the endpoint suffix, e.g. https://openrouter.ai/api/v1.
        return self.upstream_url.rsplit("/", 1)[0]


class GatewayProvenance(BaseModel):
    sequence: int = Field(ge=1)
    model: str
    enforced_provider_order: tuple[str, ...]
    actual_provider: str | None = None
    # OpenRouter's own id for the completion, taken from the `x-generation-id`
    # response header. Under an empty pin the serving provider is chosen per
    # request, so without this a score could not be attributed to any
    # particular set of weights. `GET /api/v1/generation?id=` resolves it.
    #
    # A header is not the response body: the stream is still proxied
    # byte-for-byte and nothing here inspects its content.
    generation_id: str | None = None
    status: int = Field(ge=100, le=599)


class ResponsesRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)


class GatewayProtocolError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


class ProviderGateway:
    def __init__(
        self,
        config: GatewayConfig,
        *,
        upstream_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.config = config
        self._upstream_transport = upstream_transport
        self._server: asyncio.Server | None = None
        self._client: httpx.AsyncClient | None = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._bound_port: int | None = None
        self._sequence = 0
        self.provenance: list[GatewayProvenance] = []

    @property
    def running(self) -> bool:
        return self._server is not None

    @property
    def port(self) -> int:
        if self._bound_port is None:
            raise RuntimeError("provider gateway has not started")
        return self._bound_port

    @property
    def local_url(self) -> str:
        return f"http://{self.config.bind_host}:{self.port}"

    async def __aenter__(self) -> ProviderGateway:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.stop()

    async def start(self) -> None:
        if self.running:
            raise RuntimeError("provider gateway is already running")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0),
            transport=self._upstream_transport,
        )
        try:
            self._server = await asyncio.start_server(
                self._accept,
                self.config.bind_host,
                self.config.port,
                limit=MAX_HEADER_BYTES,
            )
        except BaseException:
            await self._client.aclose()
            self._client = None
            raise
        sockets = self._server.sockets
        if not sockets:
            await self.stop()
            raise RuntimeError("provider gateway did not bind a socket")
        self._bound_port = int(sockets[0].getsockname()[1])

    async def stop(self) -> None:
        server, self._server = self._server, None
        if server is not None:
            server.close()
            await server.wait_closed()
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    def _accept(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.create_task(self._handle(reader, writer))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            method, target, headers, body = await self._read_request(reader)
            path = target.split("?", maxsplit=1)[0]
            if method != "POST" or path not in _UPSTREAM_SUFFIX:
                raise GatewayProtocolError(404, "not found")
            self._authorize(headers)
            await self._proxy(headers, body, writer, path)
        except GatewayProtocolError as error:
            await self._write_json_error(writer, error.status, str(error))
        except asyncio.IncompleteReadError, asyncio.LimitOverrunError, ValueError:
            await self._write_json_error(writer, 400, "malformed request")
        except Exception:
            LOGGER.error("provider gateway transport failure")
            await self._write_json_error(writer, 502, "upstream unavailable")
        finally:
            writer.close()
            await writer.wait_closed()

    async def _read_request(
        self, reader: asyncio.StreamReader
    ) -> tuple[str, str, dict[str, str], bytes]:
        header_block = await reader.readuntil(b"\r\n\r\n")
        if len(header_block) > MAX_HEADER_BYTES:
            raise GatewayProtocolError(431, "request headers too large")
        lines = header_block[:-4].split(b"\r\n")
        if not lines:
            raise ValueError("missing request line")
        request_line = lines[0].decode("ascii").split()
        if len(request_line) != 3 or request_line[2] != "HTTP/1.1":
            raise ValueError("invalid request line")
        headers: dict[str, str] = {}
        for raw_header in lines[1:]:
            name, separator, value = raw_header.partition(b":")
            if not separator:
                raise ValueError("invalid header")
            headers[name.decode("ascii").strip().lower()] = value.decode(
                "latin-1"
            ).strip()
        if "transfer-encoding" in headers:
            raise GatewayProtocolError(400, "chunked requests are not supported")
        content_length = int(headers.get("content-length", "0"))
        if content_length < 0 or content_length > MAX_BODY_BYTES:
            raise GatewayProtocolError(413, "request body too large")
        body = await reader.readexactly(content_length)
        return request_line[0], request_line[1], headers, body

    def _authorize(self, headers: dict[str, str]) -> None:
        expected = f"Bearer {self.config.gateway_token.get_secret_value()}"
        supplied = headers.get("authorization", "")
        if not hmac.compare_digest(supplied, expected):
            raise GatewayProtocolError(401, "unauthorized")

    async def _proxy(
        self,
        inbound_headers: dict[str, str],
        body: bytes,
        writer: asyncio.StreamWriter,
        path: str,
    ) -> None:
        try:
            raw_payload = json.loads(body)
            request = ResponsesRequest.model_validate(raw_payload)
        except (json.JSONDecodeError, ValidationError) as error:
            raise GatewayProtocolError(400, "invalid Responses request") from error
        if not isinstance(raw_payload, dict):
            raise GatewayProtocolError(400, "invalid Responses request")
        full_model = MODEL_ALIASES.get(
            request.model, DIAGNOSTIC_ALIASES.get(request.model, request.model)
        )
        providers = MODEL_PROVIDERS.get(full_model)
        if providers is None:
            raise GatewayProtocolError(400, "unsupported model")
        raw_payload["model"] = full_model
        if providers:
            raw_payload["provider"] = {
                "order": list(providers),
                "allow_fallbacks": False,
            }
        else:
            # An EMPTY pin means route automatically, and it is a deliberate
            # entry in `MODEL_PROVIDERS` rather than a missing one -- a model
            # this gateway does not know still raises above.
            #
            # The pin exists because a bare model id routes to whatever the
            # account defaults to, which 404s or serves different weights.
            # Auto-routing gives that up on purpose, for a tier whose pinned
            # endpoints this key can no longer reach at all: of 16 endpoints
            # listed for kimi-k3, fifteen 404 on this account's guardrail or
            # rate-limit, and three sweeps died having measured nothing.
            # A score from a reachable provider beats no score from an
            # unreachable one, provided the reader can tell WHICH -- which is
            # what `generation_id` below is for.
            raw_payload.pop("provider", None)
        outbound_headers = {
            name: value
            for name, value in inbound_headers.items()
            if name not in HOP_BY_HOP_HEADERS | {"authorization", "host"}
        }
        outbound_headers["authorization"] = (
            f"Bearer {self.config.openrouter_api_key.get_secret_value()}"
        )
        client = self._client
        if client is None:
            raise RuntimeError("provider gateway is not running")
        upstream_request = client.build_request(
            "POST",
            self.config.upstream_base + _UPSTREAM_SUFFIX[path],
            headers=outbound_headers,
            content=json.dumps(raw_payload, separators=(",", ":")).encode(),
        )
        try:
            response = await client.send(upstream_request, stream=True)
        except httpx.HTTPError as error:
            self._record(full_model, providers, 502)
            raise GatewayProtocolError(502, "upstream unavailable") from error
        try:
            self._record(
                full_model,
                providers,
                response.status_code,
                response.headers.get("x-generation-id"),
            )
            response_headers = [
                (name, value)
                for name, value in response.headers.multi_items()
                if name.lower() not in HOP_BY_HOP_HEADERS
            ]
            await self._write_headers(writer, response.status_code, response_headers)
            if response.is_stream_consumed:
                writer.write(response.content)
                await writer.drain()
            else:
                try:
                    async for chunk in response.aiter_raw():
                        writer.write(chunk)
                        await writer.drain()
                except httpx.HTTPError, ConnectionError:
                    LOGGER.error("provider gateway response stream failed")
        finally:
            await response.aclose()

    def _record(
        self,
        model: str,
        providers: tuple[str, ...],
        status: int,
        generation_id: str | None = None,
    ) -> None:
        self._sequence += 1
        record = GatewayProvenance(
            sequence=self._sequence,
            model=model,
            enforced_provider_order=providers,
            # The Responses stream is proxied byte-for-byte, so the gateway
            # does not inspect response content to infer the serving provider.
            actual_provider=None,
            generation_id=generation_id,
            status=status,
        )
        self.provenance.append(record)
        LOGGER.info("%s", record.model_dump_json())

    async def _write_json_error(
        self, writer: asyncio.StreamWriter, status: int, message: str
    ) -> None:
        if writer.is_closing():
            return
        body = json.dumps(
            {"error": {"message": message}}, separators=(",", ":")
        ).encode()
        await self._write_headers(
            writer,
            status,
            [("content-type", "application/json"), ("content-length", str(len(body)))],
        )
        writer.write(body)
        await writer.drain()

    async def _write_headers(
        self,
        writer: asyncio.StreamWriter,
        status: int,
        headers: list[tuple[str, str]],
    ) -> None:
        try:
            phrase = HTTPStatus(status).phrase
        except ValueError:
            phrase = "Upstream Response"
        lines = [f"HTTP/1.1 {status} {phrase}\r\n"]
        lines.extend(f"{name}: {value}\r\n" for name, value in headers)
        lines.append("connection: close\r\n\r\n")
        writer.write("".join(lines).encode("latin-1"))
        await writer.drain()
