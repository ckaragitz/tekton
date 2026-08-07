#!/usr/bin/env python3
"""Tiny local file server for feeding acceptance .rvt files to the browser.

Serves experiments/acceptance/ on 127.0.0.1 with permissive CORS and
Private-Network-Access headers so a page script on an https origin
(viewer.autodesk.com) can fetch() the bytes and hand them to the site's
own file input. Used by the automated Autodesk-Viewer upload loop.
"""
import http.server
import os
import socketserver
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "experiments", "acceptance")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + (fmt % args) + "\n")


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    sys.stderr.write(f"serving {ROOT} on http://127.0.0.1:{PORT}\n")
    httpd.serve_forever()
