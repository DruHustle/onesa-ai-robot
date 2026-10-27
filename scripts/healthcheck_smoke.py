"""Exercise the final image's health command without application data or network access."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROBE_SERVER = r"""
import http.server, os, subprocess, threading, time

mode = 200
seen = []

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        seen.append(self.path)
        if mode == 'timeout':
            time.sleep(10)
        self.send_response(mode if isinstance(mode, int) else 200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        try:
            self.wfile.write(b'{}')
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass

server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
server.daemon_threads = True
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
env = dict(os.environ, PORT=str(server.server_port), no_proxy='', NO_PROXY='')
for key in ('http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'ALL_PROXY'):
    env[key] = 'http://127.0.0.1:1'
command = ['sh', '-c', PROBE[1]] if PROBE[0] == 'CMD-SHELL' else PROBE[1:]

def check(expected_success):
    start = time.monotonic()
    result = subprocess.run(command, env=env, capture_output=True, timeout=DEADLINE + 1)
    assert (result.returncode == 0) == expected_success, 'unexpected health result'
    assert time.monotonic() - start < DEADLINE, 'probe exceeded container deadline'

try:
    check(True)
    assert seen == [EXPECTED_PATH], 'health route or request count changed'
    for mode in (503, 404, 'timeout'):
        check(False)
finally:
    server.shutdown()
    server.server_close()
check(False)
print('PASS: custom port, GET route, proxy isolation, HTTP 503/404, timeout, refusal')
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    image = parser.parse_args().image
    config = json.loads(
        subprocess.check_output(["docker", "image", "inspect", image], text=True)
    )[0]["Config"]
    health = config["Healthcheck"]
    expected = "/api/v1/ready" if ROOT.name == "onesa-ai-robot" else "/core-ready"
    probes = [("default", health["Test"], expected, health["Timeout"] / 1e9)]
    compose = json.loads((ROOT / "compose.oracle-backend.yaml").read_text())
    stage = compose["services"]["staging"].get("healthcheck")
    if stage is not None:
        # Resolve only Compose's literal-dollar escape, without host interpolation.
        command = [value.replace("$$", "$") for value in stage["test"]]
        probes.append(("staging", command, "/health", health["Timeout"] / 1e9))
    for name, command, path, deadline in probes:
        script = (
            f"PROBE = {command!r}\nEXPECTED_PATH = {path!r}\nDEADLINE = {deadline!r}\n"
            + PROBE_SERVER
        )
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--no-healthcheck",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "64",
                "--memory",
                "128m",
                "-i",
                image,
                "python",
                "-",
            ],
            input=script,
            text=True,
            capture_output=True,
            timeout=35,
            check=True,
        )
        print(name + ": " + result.stdout.strip())


if __name__ == "__main__":
    main()
