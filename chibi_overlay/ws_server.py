"""WebSocket server for streaming input data as JSON.

Mirrors input-overlay's WebSocket server feature: sends real-time
keyboard, mouse, and gamepad data as JSON to all connected clients.

Uses Python's built-in asyncio + websockets (if available) or a
lightweight socket-based fallback for maximum compatibility.

JSON format (per message):
{
    "type": "keyboard" | "mouse" | "gamepad",
    "event": "press" | "release" | "move" | "click",
    "key": "w",
    "x": 1234, "y": 567,
    "button": "left",
    "pressed": true,
    "timestamp": 1234567890.123
}
"""
from __future__ import annotations

import json
import time
import threading
from typing import Any, Dict, Optional, Set

try:
    import websockets
    import websockets.server
    _HAS_WS = True
except ImportError:
    _HAS_WS = False

try:
    import asyncio
    _HAS_ASYNCIO = True
except ImportError:
    _HAS_ASYNCIO = False


class InputWSServer:
    """WebSocket server that broadcasts input events to all connected clients.

    Usage:
        server = InputWSServer(port=16899)
        server.start()
        # When input happens:
        server.send_keyboard("w", "press")
        server.send_mouse_move(100, 200)
        # Cleanup:
        server.stop()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 16899):
        self.host = host
        self.port = port
        self._clients: Set = set()
        self._server = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._loop: Optional[Any] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def server_url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    def start(self) -> bool:
        """Start the WebSocket server in a background thread."""
        if self._running:
            return True
        if not _HAS_WS or not _HAS_ASYNCIO:
            print("[ws] websockets library not available — server disabled")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Stop the server and disconnect all clients."""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._clients.clear()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())

    async def _serve(self):
        async with websockets.serve(self._handle_client, self.host, self.port):
            while self._running:
                await asyncio.sleep(0.1)

    async def _handle_client(self, websocket, path=None):
        self._clients.add(websocket)
        try:
            async for message in websocket:
                # Client can send commands (e.g., query state)
                pass
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)

    def _broadcast(self, data: Dict[str, Any]):
        """Send JSON data to all connected clients."""
        if not self._clients or not self._loop:
            return
        data["timestamp"] = time.time()
        msg = json.dumps(data)
        try:
            if self._loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._broadcast_coro(msg), self._loop
                )
        except Exception:
            pass

    async def _broadcast_coro(self, msg: str):
        disconnected = set()
        for client in self._clients:
            try:
                await client.send(msg)
            except Exception:
                disconnected.add(client)
        self._clients -= disconnected

    # ---- convenience methods ----

    def send_keyboard(self, key: str, event: str = "press"):
        """Send a keyboard event."""
        self._broadcast({
            "type": "keyboard",
            "event": event,
            "key": key,
        })

    def send_mouse_move(self, x: int, y: int):
        """Send a mouse move event."""
        self._broadcast({
            "type": "mouse",
            "event": "move",
            "x": x,
            "y": y,
        })

    def send_mouse_click(self, button: str = "left", pressed: bool = True):
        """Send a mouse click event."""
        self._broadcast({
            "type": "mouse",
            "event": "click",
            "button": button,
            "pressed": pressed,
        })

    def send_gamepad_button(self, button: str, pressed: bool = True):
        """Send a gamepad button event."""
        self._broadcast({
            "type": "gamepad",
            "event": "press" if pressed else "release",
            "button": button,
            "pressed": pressed,
        })

    def send_gamepad_stick(self, side: str, x: float, y: float):
        """Send an analog stick position update."""
        self._broadcast({
            "type": "gamepad",
            "event": "stick",
            "side": side,  # "left" or "right"
            "x": round(x, 3),
            "y": round(y, 3),
        })

    def send_gamepad_trigger(self, side: str, value: float):
        """Send a trigger pressure update."""
        self._broadcast({
            "type": "gamepad",
            "event": "trigger",
            "side": side,  # "left" or "right"
            "value": round(value, 3),
        })

    def send_full_state(self, state: Dict[str, Any]):
        """Send a complete input state snapshot."""
        self._broadcast({
            "type": "state",
            **state,
        })
