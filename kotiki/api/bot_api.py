import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)

CCTL_RESPONSE_TIMEOUT = 10.0

# Set via configure() from config
_CCTL_SECRET: str = ""


def configure(api_secret: str) -> None:
    """Configure bot API with secret from config. Call before starting the server."""
    global _CCTL_SECRET
    _CCTL_SECRET = api_secret

app = FastAPI(title="Kotiki Bot API")


@dataclass
class CctlConnection:
    """A single cctl WebSocket connection with response waiting."""

    websocket: WebSocket
    client_id: str
    pending_response: Optional[asyncio.Future] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def deliver_response(self, data: dict) -> None:
        """Deliver received response to waiter if any."""
        if self.pending_response and not self.pending_response.done():
            self.pending_response.set_result(data)
            self.pending_response = None


class CctlConnectionManager:
    """Tracks cctl WebSocket connections and supports sending commands with response waiting."""

    def __init__(self):
        self._connections: dict[str, set[CctlConnection]] = defaultdict(set)

    def register(self, client_id: str, connection: CctlConnection) -> None:
        self._connections[client_id].add(connection)

    def unregister(self, client_id: str, connection: CctlConnection) -> None:
        self._connections[client_id].discard(connection)
        if not self._connections[client_id]:
            del self._connections[client_id]
        if connection.pending_response and not connection.pending_response.done():
            connection.pending_response.set_exception(ConnectionError("Connection closed"))

    async def _send_to_connection(
        self, conn: CctlConnection, client_id: str, payload: dict
    ) -> tuple[dict, bool]:
        """
        Send to a single connection and wait for response.
        Returns (result_dict, is_dead) - is_dead=True means connection should be unregistered.
        """
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        conn.pending_response = future
        try:
            await conn.websocket.send_json(payload)
            try:
                response = await asyncio.wait_for(future, timeout=CCTL_RESPONSE_TIMEOUT)
                if "error" in response:
                    return (
                        {"client_id": client_id, "ok": False, "response": response, "error": response["error"]},
                        False,
                    )
                return (
                    {"client_id": client_id, "ok": True, "response": response, "error": None},
                    False,
                )
            except asyncio.TimeoutError:
                return ({"client_id": client_id, "ok": False, "response": None, "error": "timeout"}, False)
        except Exception as e:
            log.warning("Failed to send to cctl %s: %s", client_id, e)
            return ({"client_id": client_id, "ok": False, "response": None, "error": str(e)}, True)
        finally:
            conn.pending_response = None

    async def send_to_id(self, client_id: str, payload: dict) -> list[dict]:
        """
        Send payload to all sockets with given id, wait for responses concurrently (10s timeout).
        Returns list of results: [{"client_id": str, "ok": bool, "response": dict | None, "error": str | None}]
        """
        if client_id not in self._connections:
            return []
        conns = list(self._connections[client_id])
        results_and_dead = await asyncio.gather(
            *[self._send_to_connection(conn, client_id, payload) for conn in conns]
        )
        results = [r for r, _ in results_and_dead]
        for (_, is_dead), conn in zip(results_and_dead, conns):
            if is_dead:
                self.unregister(client_id, conn)
        return results

    async def broadcast(self, payload: dict) -> list[dict]:
        """Send payload to all connected cctl sockets concurrently, wait for responses (no stacking)."""
        tasks = []
        conn_map: list[tuple[CctlConnection, str]] = []
        for client_id in list(self._connections.keys()):
            for conn in list(self._connections[client_id]):
                tasks.append(self._send_to_connection(conn, client_id, payload))
                conn_map.append((conn, client_id))
        results_and_dead = await asyncio.gather(*tasks)
        results = [r for r, _ in results_and_dead]
        for (_, is_dead), (conn, client_id) in zip(results_and_dead, conn_map):
            if is_dead:
                self.unregister(client_id, conn)
        return results


cctl_manager = CctlConnectionManager()


def _compute_expected_hash(client_id: str) -> str:
    if not _CCTL_SECRET:
        raise RuntimeError("Bot API not configured: call configure(api_secret=...) before use")
    return hashlib.sha1((_CCTL_SECRET + client_id).encode()).hexdigest()


@app.get("/bot_api")
async def api_root():
    """Health/root endpoint for the bot API."""
    return {"status": "ok", "api": "bot_api"}


async def _receive_loop(connection: CctlConnection) -> None:
    """Receive messages from client and deliver to pending response waiter."""
    try:
        while True:
            data = await connection.websocket.receive_json()
            connection.deliver_response(data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning("cctl receive error for %s: %s", connection.client_id, e)
        if connection.pending_response and not connection.pending_response.done():
            connection.pending_response.set_exception(e)


@app.websocket("/bot_api/cctl/{hash}/{id}")
async def cctl_websocket(
    websocket: WebSocket,
    hash: str,  # sha1(secret + id)
    id: str,
):
    expected = _compute_expected_hash(id)
    if hash != expected:
        log.warning("Invalid hash for cctl connection, id=%s", id)
        await websocket.close(code=4001, reason="Invalid hash")
        return

    await websocket.accept()
    connection = CctlConnection(websocket=websocket, client_id=id)
    cctl_manager.register(id, connection)
    log.info("cctl WebSocket connected: id=%s", id)
    recv_task = asyncio.create_task(_receive_loop(connection))

    try:
        while True:
            # Send dummy events periodically
            for i in range(5):
                event = {
                    "type": "dummy",
                    "seq": i + 1,
                    "payload": {"message": f"Dummy event {i + 1}", "ts": time.time()},
                }
                await websocket.send_json(event)
                await asyncio.sleep(2)
    except WebSocketDisconnect:
        log.info("cctl WebSocket disconnected: id=%s", id)
    except Exception as e:
        log.exception("cctl WebSocket error: %s", e)
        try:
            await websocket.close()
        except Exception:
            pass
    finally:
        recv_task.cancel()
        try:
            await recv_task
        except asyncio.CancelledError:
            pass
        cctl_manager.unregister(id, connection)
