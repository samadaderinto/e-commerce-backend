"""Minimal Prometheus exporter for Docker Desktop container resource stats."""
import http.client
import json
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SOCKET_PATH = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")


class DockerConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__("localhost", timeout=8)

    def connect(self):
        import socket

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(SOCKET_PATH)


def docker_json(path):
    connection = DockerConnection()
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"Docker API returned {response.status} for {path}")
        return json.load(response)
    finally:
        connection.close()


def escape(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def sample(container):
    stats = docker_json(f"/v1.41/containers/{container['Id']}/stats?stream=false")
    labels = container.get("Labels") or {}
    service = labels.get("com.docker.compose.service", "")
    project = labels.get("com.docker.compose.project", "")
    name = (container.get("Names") or [container["Id"][:12]])[0].lstrip("/")
    metric_labels = (
        f'name="{escape(name)}",'
        f'container_label_com_docker_compose_project="{escape(project)}",'
        f'container_label_com_docker_compose_service="{escape(service)}"'
    )
    memory = stats.get("memory_stats") or {}
    memory_details = memory.get("stats") or {}
    inactive = memory_details.get("inactive_file", 0)
    usage = max(0, memory.get("usage", 0) - inactive)
    limit = memory.get("limit", 0)
    cpu = ((stats.get("cpu_stats") or {}).get("cpu_usage") or {}).get("total_usage", 0) / 1e9
    oom = memory_details.get("oom", memory_details.get("oom_kill", 0))
    return [
        f"container_cpu_usage_seconds_total{{{metric_labels}}} {cpu}",
        f"container_memory_working_set_bytes{{{metric_labels}}} {usage}",
        f"container_spec_memory_limit_bytes{{{metric_labels}}} {limit}",
        f"container_oom_events_total{{{metric_labels}}} {oom}",
        f"container_last_seen{{{metric_labels}}} 1",
    ]


def metrics():
    containers = docker_json("/v1.41/containers/json")
    lines = [
        "# HELP docker_exporter_up Whether the Docker API was successfully queried.",
        "# TYPE docker_exporter_up gauge",
        "docker_exporter_up 1",
    ]
    with ThreadPoolExecutor(max_workers=8) as executor:
        for result in executor.map(sample, containers):
            lines.extend(result)
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/metrics"):
            self.send_error(404)
            return
        try:
            body = metrics().encode()
            status = 200
        except Exception as error:
            body = (f"docker_exporter_up 0\n# {escape(error)}\n").encode()
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
