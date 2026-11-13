import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from pipeline.lib import fetch

PAYLOAD = bytes(range(256)) * 4096  # 1 MB


def handler(support_range: bool) -> type[BaseHTTPRequestHandler]:
    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            rng = self.headers.get("Range")
            start = int(rng.split("=")[1].rstrip("-")) if rng and support_range else 0
            if start > len(PAYLOAD):
                self.send_response(416)
                self.end_headers()
                return
            body = PAYLOAD[start:]
            self.send_response(206 if start else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_a: object) -> None:
            pass

    return H


@pytest.fixture(params=[True, False], ids=["range", "no-range"])
def server(request: pytest.FixtureRequest) -> Iterator[str]:
    srv = HTTPServer(("127.0.0.1", 0), handler(request.param))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/f"
    srv.shutdown()


def test_download_completes_and_resumes_a_partial_file(server: str, tmp_path: Path) -> None:
    dest = tmp_path / "f.bin"
    dest.with_suffix(".bin.part").write_bytes(PAYLOAD[:300_000])  # download interrotto
    fetch.download(server, dest)
    assert dest.read_bytes() == PAYLOAD
    assert not dest.with_suffix(".bin.part").exists()


def test_a_stale_partial_larger_than_the_file_restarts(tmp_path: Path) -> None:
    srv = HTTPServer(("127.0.0.1", 0), handler(True))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        dest = tmp_path / "f.bin"
        dest.with_suffix(".bin.part").write_bytes(b"x" * (len(PAYLOAD) + 10))
        fetch.download(f"http://127.0.0.1:{srv.server_port}/f", dest)
        assert dest.read_bytes() == PAYLOAD
    finally:
        srv.shutdown()
