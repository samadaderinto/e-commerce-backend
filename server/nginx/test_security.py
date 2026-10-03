"""Exercise real Nginx with isolated config, loopback ports and a stub backend."""
import contextlib
import http.client
import http.server
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parent


class Backend(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(dict(self.headers)).encode())

    def log_message(self, *args):
        pass


def _nginx_available():
    if not shutil.which("nginx"):
        return False
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "nginx.conf").write_text("events { worker_connections 10; } error_log /dev/null; http { server { listen 127.0.0.1:0; } }")
        cmd = ["nginx", "-e", str(root / "startup.log"), "-p", f"{root}/", "-c", "nginx.conf", "-t"]
        try:
            res = subprocess.run(cmd, capture_output=True, timeout=2)
            return res.returncode == 0
        except Exception:
            return False


@unittest.skipUnless(_nginx_available(), "Nginx execution not permitted in current environment")
class SecurityTests(unittest.TestCase):
    @contextlib.contextmanager
    def proxy(self, allowed="", blocked="", suspected="", trusted=""):
        with tempfile.TemporaryDirectory(prefix="nginx-security-") as directory:
            root = Path(directory)
            backend = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Backend)
            thread = threading.Thread(target=backend.serve_forever, daemon=True)
            thread.start()
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            for source in ROOT.glob("*.conf"):
                shutil.copy(source, root / source.name)
            for name, content in {"allowed-ips": allowed, "blocked-ips": blocked,
                                  "suspected-ips": suspected, "trusted-proxies": trusted}.items():
                (root / f"{name}.conf").write_text(content)
            (root / "upstream.conf").write_text(f"server 127.0.0.1:{backend.server_port};\n")
            config = (root / "nginx.conf").read_text()
            config = config.replace("listen 8080;", f"listen 127.0.0.1:{port};")
            config = config.replace("worker_processes auto;", "worker_processes 1;")
            config = config.replace("/tmp/nginx", f"{root}/nginx")
            config = config.replace("/dev/stdout", str(root / "access.log"))
            config = config.replace("/dev/stderr", str(root / "security.log"))
            (root / "nginx.conf").write_text(config)
            command = ["nginx", "-e", str(root / "startup.log"), "-p", f"{root}/", "-c", "nginx.conf"]
            process = None
            try:
                subprocess.run(command + ["-t"], check=True, capture_output=True)
                process = subprocess.Popen(command + ["-g", "daemon off;"], stderr=subprocess.PIPE)
                for _ in range(100):
                    if process.poll() is not None:
                        self.fail(process.stderr.read().decode())
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                            break
                    except OSError:
                        time.sleep(0.02)
                else:
                    self.fail("Nginx did not start")
                self.port = port
                yield root
            finally:
                if process is not None:
                    process.terminate()
                    process.communicate(timeout=5)
                backend.shutdown()
                backend.server_close()
                thread.join()

    def request(self, path="/products/", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_public_private_probes_and_spoofed_headers(self):
        with self.proxy(allowed="203.0.113.10 1;\n"):
            status, headers, body = self.request(headers={"X-Forwarded-For": "203.0.113.10"})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["X-Forwarded-For"], "127.0.0.1")
            self.assertIn("X-Request-ID", headers)
            for path in ["/admin/", "/api/docs/", "/silk/", "/.env", "/.git/config", "/wp-login.php"]:
                self.assertEqual(self.request(path, {"X-Forwarded-For": "203.0.113.10"})[0], 403)
            self.assertEqual(self.request("/.well-known/acme-challenge/test")[0], 200)

    def test_general_rate_limit(self):
        with self.proxy():
            responses = [self.request()[0] for _ in range(80)]
            self.assertEqual(responses[0], 200)
            self.assertIn(429, responses)

    def test_allowlist_and_block_precedence(self):
        with self.proxy(allowed="127.0.0.1/32 1;\n", suspected="127.0.0.0/8 1;\n"):
            self.assertTrue(all(self.request("/admin/")[0] == 200 for _ in range(8)))
        with self.proxy(allowed="127.0.0.1 1;\n", blocked="127.0.0.0/8 1;\n"):
            self.assertEqual(self.request()[0], 403)

    def test_suspected_and_auth_limits(self):
        for policies, path in [({"suspected": "127.0.0.1 1;\n"}, "/products/"),
                               ({}, "/api/v1/auth/login/"), ({}, "/reset-password/request/")]:
            with self.subTest(path=path), self.proxy(**policies):
                responses = [self.request(path) for _ in range(10)]
                self.assertEqual(responses[0][0], 200)
                self.assertIn(429, [item[0] for item in responses])
                limited = next(item for item in responses if item[0] == 429)
                self.assertEqual(limited[1]["Retry-After"], "60")

    def test_trusted_proxy_ipv6_and_log_redaction(self):
        trusted = "set_real_ip_from 127.0.0.1;\nreal_ip_header X-Forwarded-For;\nreal_ip_recursive on;\n"
        with self.proxy(trusted=trusted, blocked="2001:db8::/32 1;\n") as root:
            response = self.request("/products/?token=secret-value", {"X-Forwarded-For": "2001:db8::10"})
            self.assertEqual(response[0], 403)
            # Access logging completes just after the response is flushed.
            for _ in range(100):
                content = (root / "access.log").read_text()
                if content:
                    break
                time.sleep(0.01)
            event = json.loads(content.splitlines()[-1])
            self.assertEqual(event["client_ip"], "2001:db8::10")
            self.assertEqual(event["blocked"], 1)
            self.assertNotIn("secret-value", content)


if __name__ == "__main__":
    unittest.main()
