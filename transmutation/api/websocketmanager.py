# Copyright 2023 Badreddine LEJMI.
# SPDX-License-Identifier: 	AGPL-3.0-or-later

from fastapi import WebSocket
import json


class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return list(obj)
        return json.JSONEncoder.default(self, obj)


class WebSocketManager:
    def __init__(self):
        self.connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.connections.remove(websocket)

    async def message(self, websocket: WebSocket, message: str | dict):
        if type(message) is dict:
            message = json.dumps(message, cls=SetEncoder)
        await websocket.send_text(message)

    async def broadcast(self, message: str | dict):
        if type(message) is dict:
            message = json.dumps(message, cls=SetEncoder)
        for connection in self.connections:
            await connection.send_text(message)


manager = WebSocketManager()
