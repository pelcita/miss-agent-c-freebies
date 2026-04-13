"""
Vercel Serverless: Listet alle Freebie-Projekte von Vercel.
"""
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        token = os.environ.get("VERCEL_TOKEN", "")
        if not token:
            return self._json(500, {"error": "VERCEL_TOKEN fehlt"})

        try:
            req = urllib.request.Request(
                "https://api.vercel.com/v9/projects?limit=50",
                headers={"Authorization": f"Bearer {token}"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            # Nur Freebie-Projekte (nicht dashboard, go, etc.)
            skip = {"dashboard", "go", "miss-agent-c-freebies"}
            freebies = []
            for p in data.get("projects", []):
                name = p.get("name", "")
                if name in skip:
                    continue

                # URL zusammenbauen
                targets = p.get("targets", {})
                prod = targets.get("production", {})
                alias = prod.get("alias", [])
                url = f"https://{alias[0]}" if alias else f"https://{name}.vercel.app"

                freebies.append({
                    "name": name,
                    "title": name.replace("-", " ").title(),
                    "url": url,
                    "created": p.get("createdAt", 0),
                })

            # Neueste zuerst
            freebies.sort(key=lambda f: f["created"], reverse=True)
            self._json(200, freebies)

        except Exception as e:
            self._json(500, {"error": str(e)[:300]})

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _json(self, code, data):
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
