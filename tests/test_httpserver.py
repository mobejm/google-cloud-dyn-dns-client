import http.server

from ipaddress import ip_address, IPv4Address
from threading import Thread
from typing import Dict


class TestHttpRequestHandler:
    def __init__(
        self,
        status_code: int = 404,
        headers: Dict[str, str] = {"Content-type": "text/plain"},
        response_payload: str = "Not Found!",
    ) -> None:
        self._status_code = status_code
        self._headers = headers
        self._response_payload = response_payload
        self._request_count = 0

    @property
    def status_code(self) -> int:
        return self._status_code

    @status_code.setter
    def status_code(self, s: int) -> None:
        self._status_code = s

    @property
    def headers(self) -> Dict[str, str]:
        return self._headers

    @status_code.setter
    def headers(self, h: int) -> None:
        self._headers = h

    @property
    def response(self) -> str:
        return self._response_payload

    @property
    def request_count(self) -> int:
        return self._request_count

    @response.setter
    def response(self, r: str) -> None:
        self._response_payload = r

    def handle_request(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        self._request_count += 1
        handler.send_response(self._status_code)
        for header in self._headers.items():
            handler.send_header(header[0], header[1])
        handler.end_headers()
        handler.wfile.write(f"{self._response_payload}".encode("utf-8"))


class TestHttpServerHandler:
    def __init__(
        self, get_handler: TestHttpRequestHandler, post_handler: TestHttpRequestHandler
    ) -> None:
        self._get_handler = get_handler
        self._post_handler = post_handler

    def handle_get(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        self._get_handler.handle_request(handler)

    def handle_post(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        self._post_handler.handle_request(handler)


class TestHttpServer:
    def __init__(
        self,
        server_handler: TestHttpServerHandler,
        address: str = "localhost",
        port: int = 8181,
    ) -> None:
        self._server_address = (address, port)
        self._request_handler_class = self._build_custom_request_handler(
            handler=server_handler
        )
        self._httpd = None
        self._thread = None
        self._open = False

    @property
    def address(self) -> str:
        return self._server_address[0]

    @property
    def port(self) -> int:
        return self._server_address[1]

    @property
    def is_open(self) -> bool:
        return self._open

    def start(self) -> None:
        if not self._open:
            self._open = True
            self._httpd = http.server.HTTPServer(
                server_address=self._server_address,
                RequestHandlerClass=self._request_handler_class,
            )
            self._thread = Thread(target=self._httpd.serve_forever, args=[])
            self._thread.start()

    def stop(self) -> None:
        if self._open:
            self._httpd.server_close()
            self._httpd.shutdown()
            self._thread.join()
            self._open = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, type, value, traceback):
        self.stop()

    def _build_custom_request_handler(self, handler: TestHttpServerHandler):
        class SimpleHttpRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                handler.handle_get(self)

            def do_POST(self):
                handler.handle_post(self)

        return SimpleHttpRequestHandler
