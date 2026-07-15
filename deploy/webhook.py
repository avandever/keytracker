#!/usr/bin/env python3
"""
GitHub webhook listener for auto-deploy on push to main.

Validates the webhook signature, then runs deploy.sh in the background.
Listens on port 9867 by default (configurable via WEBHOOK_PORT env var).
"""

import hashlib
import hmac
import json
import os
import subprocess
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
DEPLOY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy.sh")
PORT = int(os.environ.get("WEBHOOK_PORT", "9867"))
DEPLOY_BRANCH = "refs/heads/main"


def verify_signature(payload: bytes, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        print("WARNING: No WEBHOOK_SECRET set, skipping signature verification", flush=True)
        return True
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/webhook":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(content_length)

        signature = self.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(payload, signature):
            print("Rejected: invalid signature", flush=True)
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid signature")
            return

        event = self.headers.get("X-GitHub-Event", "")
        if event == "ping":
            print("Received ping event", flush=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"pong")
            return

        if event != "push":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Ignored (not a push event)")
            return

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        ref = data.get("ref", "")
        if ref != DEPLOY_BRANCH:
            print(f"Ignored push to {ref} (not {DEPLOY_BRANCH})", flush=True)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Ignored (push to {ref})".encode())
            return

        pusher = data.get("pusher", {}).get("name", "unknown")
        head_commit = data.get("head_commit", {}).get("message", "").split("\n")[0]
        print(f"Deploy triggered by {pusher}: {head_commit}", flush=True)

        subprocess.Popen(
            ["bash", DEPLOY_SCRIPT],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Deploy started")

    def log_message(self, format, *args):
        print(f"[webhook] {args[0]}", flush=True)


def main():
    if not WEBHOOK_SECRET:
        print(
            "WARNING: WEBHOOK_SECRET not set. Set it to match your GitHub webhook secret.",
            file=sys.stderr,
            flush=True,
        )

    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Webhook listener started on port {PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
