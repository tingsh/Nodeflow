"""Tiny Redis-compatible TCP server for local Novena hardware tests.

This is not a production Redis replacement. It implements only the small
RESP command subset used by the local MQTT ingestion queue path.
"""

from __future__ import annotations

import socketserver
import threading
from collections import defaultdict


LISTS: dict[str, list[bytes]] = defaultdict(list)
STRINGS: dict[str, bytes] = {}
LOCK = threading.Lock()


def simple(value: str) -> bytes:
    return f"+{value}\r\n".encode()


def error(value: str) -> bytes:
    return f"-ERR {value}\r\n".encode()


def integer(value: int) -> bytes:
    return f":{value}\r\n".encode()


def bulk(value: bytes | str | None) -> bytes:
    if value is None:
        return b"$-1\r\n"
    if isinstance(value, str):
        value = value.encode()
    return b"$" + str(len(value)).encode() + b"\r\n" + value + b"\r\n"


def array(values: list[bytes | str | None | int]) -> bytes:
    out = [b"*" + str(len(values)).encode() + b"\r\n"]
    for item in values:
        if isinstance(item, int):
            out.append(integer(item))
        else:
            out.append(bulk(item))
    return b"".join(out)


class MiniRedisHandler(socketserver.StreamRequestHandler):
    queued: list[list[bytes]]

    def setup(self) -> None:
        super().setup()
        self.queued = []
        self.in_multi = False

    def handle(self) -> None:
        while True:
            command = self._read_resp_command()
            if command is None:
                return
            response = self._dispatch(command)
            self.wfile.write(response)
            self.wfile.flush()

    def _readline(self) -> bytes | None:
        line = self.rfile.readline()
        return line if line else None

    def _read_resp_command(self) -> list[bytes] | None:
        line = self._readline()
        if line is None:
            return None
        if not line:
            return None

        if line.startswith(b"*"):
            count = int(line[1:].strip())
            parts = []
            for _ in range(count):
                length_line = self._readline()
                if length_line is None or not length_line.startswith(b"$"):
                    return None
                length = int(length_line[1:].strip())
                data = self.rfile.read(length)
                self.rfile.read(2)
                parts.append(data)
            return parts

        parts = line.strip().split()
        return parts or None

    def _dispatch(self, command: list[bytes]) -> bytes:
        name = command[0].decode(errors="ignore").upper()

        if self.in_multi and name not in {"EXEC", "DISCARD", "MULTI"}:
            self.queued.append(command)
            return simple("QUEUED")

        if name == "MULTI":
            self.in_multi = True
            self.queued = []
            return simple("OK")
        if name == "DISCARD":
            self.in_multi = False
            self.queued = []
            return simple("OK")
        if name == "EXEC":
            queued = self.queued
            self.in_multi = False
            self.queued = []
            results = [self._execute(cmd, raw=True) for cmd in queued]
            return b"*" + str(len(results)).encode() + b"\r\n" + b"".join(results)

        return self._execute(command)

    def _execute(self, command: list[bytes], raw: bool = False) -> bytes:
        name = command[0].decode(errors="ignore").upper()

        try:
            if name == "PING":
                return bulk(command[1]) if len(command) > 1 else simple("PONG")
            if name in {"CLIENT", "HELLO"}:
                return simple("OK")
            if name == "INFO":
                return bulk("redis_version:7.0.0-dev-miniredis\r\n")
            if name == "SELECT":
                return simple("OK")
            if name == "QUIT":
                return simple("OK")

            if name == "RPUSH":
                key = command[1].decode()
                values = command[2:]
                with LOCK:
                    LISTS[key].extend(values)
                    return integer(len(LISTS[key]))

            if name == "LRANGE":
                key = command[1].decode()
                start = int(command[2])
                stop = int(command[3])
                with LOCK:
                    items = list(LISTS.get(key, []))
                if stop == -1:
                    subset = items[start:]
                else:
                    subset = items[start : stop + 1]
                return array(subset)

            if name in {"DEL", "DELETE"}:
                removed = 0
                with LOCK:
                    for raw_key in command[1:]:
                        key = raw_key.decode()
                        if key in LISTS:
                            removed += 1
                            del LISTS[key]
                        if key in STRINGS:
                            removed += 1
                            del STRINGS[key]
                return integer(removed)

            if name == "LLEN":
                key = command[1].decode()
                with LOCK:
                    return integer(len(LISTS.get(key, [])))

            if name == "LINDEX":
                key = command[1].decode()
                index = int(command[2])
                with LOCK:
                    items = LISTS.get(key, [])
                    try:
                        return bulk(items[index])
                    except IndexError:
                        return bulk(None)

            if name == "SET":
                key = command[1].decode()
                with LOCK:
                    STRINGS[key] = command[2]
                return simple("OK")

            if name == "GET":
                key = command[1].decode()
                with LOCK:
                    return bulk(STRINGS.get(key))

            if name in {"EXPIRE", "TTL"}:
                return integer(1 if name == "EXPIRE" else -1)
        except Exception as exc:
            return error(str(exc))

        return error(f"unsupported command {name}")


class ThreadingMiniRedis(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    with ThreadingMiniRedis(("127.0.0.1", 6379), MiniRedisHandler) as server:
        print("dev_miniredis listening on 127.0.0.1:6379", flush=True)
        server.serve_forever()
