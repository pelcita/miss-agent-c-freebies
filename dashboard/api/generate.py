"""
Vercel Serverless Function: Freebie generieren + deployen.
POST /api/generate mit JSON Body → erzeugt HTML, deployed auf Vercel, gibt URL zurück.
"""

import json
import os
import re
import urllib.request
import urllib.error
import time
import base64


# ── Brand-Farben ──────────────────────────────────────────────

HERO_COLORS = {
    "sky": "linear-gradient(135deg, #6EA8B0 0%, #88BEC5 40%, #A4CCCE 100%)",
    "orange": "linear-gradient(135deg, #DE7C30 0%, #F48225 40%, #f89b4f 100%)",
}


# ── HTML Rendering ────────────────────────────────────────────

def render_block(block):
    t = block.get("type", "text")

    if t == "text":
        return f'<p>{block["content"]}</p>'

    elif t == "subtitle":
        return f'<h3>{block["content"]}</h3>'

    elif t == "bullets":
        items = "".join(f"<li>{i}</li>" for i in block["items"])
        return f'<ul class="bullet-list">{items}</ul>'

    elif t == "numbered":
        items = "".join(f"<li>{i}</li>" for i in block["items"])
        return f'<ol class="numbered-list">{items}</ol>'

    elif t == "tip":
        return f'<div class="tip-box"><p><strong>Tipp:</strong> {block["content"]}</p></div>'

    elif t == "warning":
        return f'<div class="warning-box"><p><strong>Wichtig:</strong> {block["content"]}</p></div>'

    elif t == "prompt":
        label = block.get("label", "Prompt")
        return (
            f'<div class="prompt-box">'
            f'<div class="prompt-box-header"><span>{label}</span>'
            f'<button class="copy-btn">Kopieren</button></div>'
            f'<div class="prompt-box-content">{block["content"]}</div></div>'
        )

    elif t == "cards":
        cards = "".join(
            f'<div class="card"><div class="card-icon">{c.get("icon","")}</div>'
            f'<h4>{c["title"]}</h4><p>{c.get("desc","")}</p></div>'
            for c in block["items"]
        )
        return f'<div class="card-grid">{cards}</div>'

    elif t == "spacer":
        return '<div class="divider"></div>'

    return ""


def render_sections(sections):
    parts = []
    for i, s in enumerate(sections, 1):
        blocks = "".join(render_block(b) for b in s.get("blocks", []))
        parts.append(
            f'<section class="section" id="section-{i}">'
            f'<div class="section-header">'
            f'<div class="section-number">{i}</div>'
            f'<h2>{s["title"]}</h2></div>{blocks}</section>'
        )
    return "".join(parts)


def render_toc(sections):
    items = "".join(
        f'<li><span class="toc-num">{i}</span>'
        f'<a href="#section-{i}">{s["title"]}</a></li>'
        for i, s in enumerate(sections, 1)
    )
    return items


def render_tags(tags):
    if not tags:
        tags = ["Sofort einsetzbar", "Praxiserprobt", "Kostenlos"]
    return "".join(f'<span class="hero-tag">{t}</span>' for t in tags)


def build_html(title, description, sections, tags, hero_color):
    """Baut die komplette Freebie HTML-Seite."""
    hero_bg = HERO_COLORS.get(hero_color, HERO_COLORS["sky"])

    # Template inline (um Dateisystem-Zugriff zu vermeiden)
    return f'''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} | Miss Agent C</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title} | Miss Agent C">
<meta property="og:description" content="{description}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,800;1,700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root{{--sky:#88BEC5;--sky-light:#A4CCCE;--orange:#F48225;--orange-light:#f89b4f;--golden:#EFA818;--deep-orange:#DE7C30;--navy:#091440;--warm-white:#FFF9ED;--white:#FFFFFF;--text:#091440;--text-light:#3d4f6f;--text-muted:#6b7a94;--border:#e2e8f0;--code-bg:#f0f4f5}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',-apple-system,sans-serif;background:var(--warm-white);color:var(--text);font-size:16px;line-height:1.7}}
.hero{{background:{hero_bg};color:var(--white);padding:3rem 1.5rem 4rem;text-align:center;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;top:-50%;right:-20%;width:500px;height:500px;background:radial-gradient(circle,rgba(255,255,255,0.08) 0%,transparent 70%);border-radius:50%}}
.hero-brand{{font-size:0.85rem;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;margin-bottom:1.5rem}}
.hero-badge{{display:inline-block;background:var(--orange);padding:0.35rem 1rem;border-radius:50px;font-size:0.75rem;font-weight:700;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:1.5rem}}
.hero h1{{font-family:'Playfair Display',serif;font-size:clamp(2rem,5vw,3.2rem);font-weight:800;line-height:1.15;margin-bottom:1rem;max-width:700px;margin-left:auto;margin-right:auto}}
.hero-desc{{font-size:1.05rem;opacity:0.9;max-width:560px;margin:0 auto 2rem;line-height:1.6}}
.hero-tags{{display:flex;flex-wrap:wrap;justify-content:center;gap:0.5rem}}
.hero-tag{{background:rgba(255,255,255,0.12);padding:0.3rem 0.9rem;border-radius:8px;font-size:0.8rem;font-weight:500}}
.main{{max-width:780px;margin:0 auto;padding:0 1.5rem}}
.toc{{background:var(--white);border:1px solid var(--border);border-radius:16px;padding:2rem;margin:-2rem auto 3rem;position:relative;z-index:2;box-shadow:0 4px 20px rgba(9,20,64,0.06)}}
.toc h2{{font-family:'Playfair Display',serif;font-size:1.2rem;margin-bottom:1rem;color:var(--navy)}}
.toc-list{{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:0.6rem}}
.toc-list li{{display:flex;align-items:center;gap:0.6rem}}
.toc-num{{width:26px;height:26px;background:var(--orange);color:white;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:0.75rem;font-weight:700;flex-shrink:0}}
.toc-list a{{color:var(--text-light);text-decoration:none;font-size:0.9rem;font-weight:500;transition:color 0.2s}}
.toc-list a:hover{{color:var(--orange)}}
.section{{margin-bottom:3.5rem}}
.section-header{{display:flex;align-items:center;gap:0.75rem;margin-bottom:1.5rem}}
.section-number{{width:36px;height:36px;background:var(--orange);color:white;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:0.95rem;font-weight:800;flex-shrink:0}}
.section h2{{font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;color:var(--navy)}}
.section h3{{font-size:1.1rem;font-weight:700;color:var(--navy);margin:1.8rem 0 0.6rem}}
.section p{{color:var(--text-light);margin-bottom:1rem}}
.bullet-list{{list-style:none;margin:1rem 0 1.5rem}}
.bullet-list li{{display:flex;align-items:flex-start;gap:0.75rem;padding:0.5rem 0;color:var(--text-light)}}
.bullet-list li::before{{content:'';width:8px;height:8px;background:var(--sky);border-radius:50%;flex-shrink:0;margin-top:0.45rem}}
.numbered-list{{list-style:none;counter-reset:step;margin:1rem 0 1.5rem}}
.numbered-list li{{counter-increment:step;display:flex;align-items:flex-start;gap:0.75rem;padding:0.5rem 0;color:var(--text-light)}}
.numbered-list li::before{{content:counter(step);width:28px;height:28px;background:var(--orange);color:white;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:0.8rem;font-weight:700;flex-shrink:0}}
.tip-box{{background:linear-gradient(135deg,#e8f4f5,#d4ecee);border-left:4px solid var(--sky);border-radius:0 12px 12px 0;padding:1.2rem 1.5rem;margin:1.5rem 0}}
.tip-box p{{color:var(--text);margin:0;font-size:0.95rem}}
.tip-box strong{{color:#6EA8B0}}
.warning-box{{background:linear-gradient(135deg,#fff5eb,#feecd6);border-left:4px solid var(--orange);border-radius:0 12px 12px 0;padding:1.2rem 1.5rem;margin:1.5rem 0}}
.warning-box p{{color:var(--text);margin:0;font-size:0.95rem}}
.warning-box strong{{color:var(--deep-orange)}}
.prompt-box{{background:var(--white);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin:1.5rem 0}}
.prompt-box-header{{background:var(--navy);color:var(--white);padding:0.6rem 1.2rem;font-size:0.75rem;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;display:flex;align-items:center;justify-content:space-between}}
.prompt-box-header .copy-btn{{background:rgba(255,255,255,0.15);border:none;color:white;padding:0.25rem 0.75rem;border-radius:6px;font-size:0.75rem;cursor:pointer}}
.prompt-box-header .copy-btn:hover{{background:rgba(255,255,255,0.25)}}
.prompt-box-content{{padding:1.2rem 1.5rem;font-family:'Courier New',monospace;font-size:0.9rem;line-height:1.6;color:var(--text-light);white-space:pre-wrap}}
.card-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin:1.5rem 0}}
.card{{background:var(--white);border:1px solid var(--border);border-radius:14px;padding:1.5rem;text-align:center;transition:all 0.3s}}
.card:hover{{border-color:var(--sky);transform:translateY(-2px);box-shadow:0 8px 24px rgba(9,20,64,0.08)}}
.card-icon{{font-size:2rem;margin-bottom:0.75rem}}
.card h4{{font-size:0.95rem;font-weight:700;color:var(--navy);margin-bottom:0.4rem}}
.card p{{font-size:0.85rem;color:var(--text-muted);margin:0}}
.divider{{height:1px;background:var(--border);margin:3rem 0}}
.cta-footer{{background:linear-gradient(135deg,var(--orange),var(--deep-orange));color:white;border-radius:20px;padding:3rem 2rem;text-align:center;margin:2rem 0 3rem}}
.cta-footer h2{{font-family:'Playfair Display',serif;font-size:1.8rem;margin-bottom:1rem}}
.cta-footer p{{color:rgba(255,255,255,0.9);margin-bottom:1.5rem;max-width:480px;margin-left:auto;margin-right:auto}}
.cta-links{{display:flex;flex-wrap:wrap;justify-content:center;gap:0.75rem}}
.cta-link{{display:inline-flex;align-items:center;gap:0.5rem;background:var(--white);color:var(--navy);padding:0.85rem 1.8rem;border-radius:12px;font-weight:700;font-size:0.95rem;text-decoration:none;transition:all 0.2s}}
.cta-link:hover{{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,0.15)}}
.cta-link.secondary{{background:rgba(255,255,255,0.15);color:white}}
.cta-link.secondary:hover{{background:rgba(255,255,255,0.25)}}
.footer{{text-align:center;padding:2rem 1.5rem;color:var(--text-muted);font-size:0.8rem;border-top:1px solid var(--border)}}
.footer a{{color:var(--orange);text-decoration:none}}
@media(max-width:600px){{.hero{{padding:2rem 1rem 3rem}}.toc-list{{grid-template-columns:1fr}}.card-grid{{grid-template-columns:1fr}}.section h2{{font-size:1.3rem}}.cta-links{{flex-direction:column;align-items:center}}}}
.copy-btn.copied{{background:rgba(136,190,197,0.4)!important}}
</style>
</head>
<body>
<header class="hero">
<div class="hero-brand">@miss.agent.c</div>
<div class="hero-badge">Kostenloses Freebie</div>
<h1>{title}</h1>
<p class="hero-desc">{description}</p>
<div class="hero-tags">{render_tags(tags)}</div>
</header>
<div class="main">
<nav class="toc"><h2>Inhalt</h2><ul class="toc-list">{render_toc(sections)}</ul></nav>
{render_sections(sections)}
<section class="cta-footer">
<h2>Bereit f&uuml;r mehr?</h2>
<p>Tritt der kostenlosen Community bei und hol dir weitere Freebies, Vorlagen und KI-Tipps.</p>
<div class="cta-links">
<a href="https://www.skool.com/ag3nt-c-2041/about" class="cta-link" target="_blank">Zur Community</a>
<a href="https://instagram.com/miss.agent.c" class="cta-link secondary" target="_blank">@miss.agent.c folgen</a>
<a href="https://blotato.com/?ref=olgai3" class="cta-link secondary" target="_blank">Blotato &mdash; KI &amp; Social Media Tool</a>
</div>
</section>
</div>
<footer class="footer">
<p>&copy; 2026 <a href="https://instagram.com/miss.agent.c">@miss.agent.c</a> &middot; Head Up High GmbH &middot; Olga Reyes-Busch</p>
<p style="margin-top:0.4rem"><a href="https://www.skool.com/ag3nt-c-2041/about">Community</a> &middot; <a href="https://blotato.com/?ref=olgai3">Blotato</a></p>
</footer>
<script>
document.addEventListener('click',function(e){{if(e.target.classList.contains('copy-btn')){{const box=e.target.closest('.prompt-box');const text=box.querySelector('.prompt-box-content').textContent;navigator.clipboard.writeText(text.trim()).then(()=>{{e.target.textContent='Kopiert!';e.target.classList.add('copied');setTimeout(()=>{{e.target.textContent='Kopieren';e.target.classList.remove('copied')}},2000)}});}}}});
</script>
</body>
</html>'''


# ── Vercel Deploy API ─────────────────────────────────────────

def deploy_to_vercel(name, html_content, vercel_token):
    """Deployed die HTML-Datei als neues Vercel-Projekt via API."""

    # File als base64
    html_b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")

    payload = {
        "name": name,
        "files": [
            {
                "file": "index.html",
                "data": html_b64,
                "encoding": "base64"
            }
        ],
        "projectSettings": {
            "framework": None
        },
        "target": "production"
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.vercel.com/v13/deployments",
        data=data,
        headers={
            "Authorization": f"Bearer {vercel_token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {
                "url": f"https://{result.get('url', '')}",
                "alias": result.get("alias", []),
                "id": result.get("id", ""),
                "ready": result.get("readyState", ""),
            }
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {"error": f"Vercel API Error {e.code}: {error_body}"}
    except Exception as e:
        return {"error": str(e)}


# ── Update Redirect ───────────────────────────────────────────

def update_redirect(keyword, freebie_url, vercel_token):
    """
    Liest die aktuelle go/index.html, fügt das neue Keyword ein, re-deployed.
    """
    # Aktuelle Redirect-Datei von Vercel holen
    try:
        req = urllib.request.Request(
            "https://go-bay.vercel.app/",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            redirect_html = resp.read().decode("utf-8")
    except Exception:
        return {"error": "Konnte Redirect-Service nicht laden"}

    keyword_upper = keyword.upper()

    # Prüfen ob Keyword schon existiert
    if f'"{keyword_upper}"' in redirect_html:
        # URL aktualisieren
        import re as re_mod
        redirect_html = re_mod.sub(
            f'"{keyword_upper}":\\s*"[^"]*"',
            f'"{keyword_upper}":  "{freebie_url}"',
            redirect_html
        )
    else:
        # Neues Keyword einfügen
        marker = "// Neue Freebies hier einfügen:"
        if marker in redirect_html:
            entry = f'            "{keyword_upper}":  "{freebie_url}",\n            {marker}'
            redirect_html = redirect_html.replace(marker, entry)

    # Redirect re-deployen
    html_b64 = base64.b64encode(redirect_html.encode("utf-8")).decode("ascii")

    # vercel.json für den redirect service
    vercel_json = json.dumps({
        "version": 2,
        "builds": [{"src": "index.html", "use": "@vercel/static"}],
        "routes": [{"src": "/(.*)", "dest": "/index.html"}]
    })
    vercel_json_b64 = base64.b64encode(vercel_json.encode("utf-8")).decode("ascii")

    payload = {
        "name": "go",
        "files": [
            {"file": "index.html", "data": html_b64, "encoding": "base64"},
            {"file": "vercel.json", "data": vercel_json_b64, "encoding": "base64"},
        ],
        "projectSettings": {"framework": None},
        "target": "production"
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.vercel.com/v13/deployments",
        data=data,
        headers={
            "Authorization": f"Bearer {vercel_token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return {"ok": True, "redirect_url": f"https://go-bay.vercel.app/go/{keyword_upper}"}
    except Exception as e:
        return {"error": str(e)}


# ── Vercel Serverless Handler (WSGI-style for @vercel/python) ─

from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors()
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
        except Exception:
            self._respond(400, {"error": "Ungültiges JSON"})
            return

        # Pflichtfelder
        title = body.get("title", "").strip()
        keyword = body.get("keyword", "FREEBIE").strip().upper()
        description = body.get("description", "").strip()
        sections = body.get("sections", [])
        tags = body.get("tags", [])
        hero_color = body.get("heroColor", "sky")

        if not title:
            self._respond(400, {"error": "Titel fehlt"})
            return

        # Slug
        name = title.lower()
        for old, new in [("ä","ae"),("ö","oe"),("ü","ue"),("ß","ss")]:
            name = name.replace(old, new)
        name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")

        # Vercel Token
        vercel_token = os.environ.get("VERCEL_TOKEN", "")
        if not vercel_token:
            self._respond(500, {"error": "VERCEL_TOKEN nicht konfiguriert"})
            return

        # 1. HTML generieren
        html = build_html(title, description, sections, tags, hero_color)

        # 2. Zu Vercel deployen
        deploy_result = deploy_to_vercel(name, html, vercel_token)
        if "error" in deploy_result:
            self._respond(500, deploy_result)
            return

        freebie_url = deploy_result["url"]

        # 3. Redirect aktualisieren
        redirect_result = update_redirect(keyword, freebie_url, vercel_token)

        # 4. Erfolg
        self._respond(200, {
            "success": True,
            "name": name,
            "title": title,
            "keyword": keyword,
            "freebie_url": freebie_url,
            "redirect_url": f"https://go-bay.vercel.app/go/{keyword}",
            "redirect_updated": redirect_result.get("ok", False),
        })

    def _respond(self, code, data):
        self.send_response(code)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
