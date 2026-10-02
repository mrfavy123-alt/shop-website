"""Vercel adapter for the existing shop HTTP handlers."""
import json
from http.server import BaseHTTPRequestHandler

from server import Handler as ShopHandler, supabase_settings


class VercelShopHandler(BaseHTTPRequestHandler):
    """Forward Vercel function requests through the shop's existing API code."""

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def json_response(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        ShopHandler.do_GET(self)

    def do_POST(self):
        url, public_key, secret_key = supabase_settings()
        if not (url and public_key and secret_key):
            self.json_response(503, {
                "error": "The shop database is not configured. Add the Supabase environment variables in Vercel and redeploy."
            })
            return
        ShopHandler.do_POST(self)
