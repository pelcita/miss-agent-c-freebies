"""
Freebie Dashboard — Lokale App
Läuft auf deinem Rechner, hat Zugriff auf Claude API + Vercel CLI.

Starten: python app.py
Öffnen: http://localhost:5000
"""

import json
import os
import re
import subprocess
import sys
import io
import time
import base64
import urllib.request
import urllib.error
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
# Expliziter Pfad damit es im Flask Debug-Mode funktioniert
_env_path = Path("A:/Freebies/.env")
if not _env_path.exists():
    _env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(str(_env_path), override=True)

from flask import Flask, request, jsonify, send_file, send_from_directory
import anthropic

# Flask app

app = Flask(__name__, static_folder=".", static_url_path="")

# Pfade
BASE_DIR = Path(__file__).parent.parent  # A:\Freebies
TEMPLATE_PATH = BASE_DIR / "template.html"
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")

# ── Claude API ────────────────────────────────────────────────

SYSTEM_PROMPT = """Du bist der Content-Ersteller für Miss Agent C (@miss.agent.c).
Du erstellst kompakte, hochwertige Freebies die sofort Mehrwert liefern.

STIL:
- Kompakt und intensiv — jeder Satz muss Wert liefern, kein Fülltext
- Scanbar: Leute LESEN nicht, sie SCANNEN. Nutze Bullets, Cards, kurze Absätze
- Max 3-4 Sektionen — lieber weniger aber knackiger
- Pro Sektion: 1 kurzer Einleitungssatz, dann direkt Bullets/Prompts/Cards
- Fließtext MAXIMAL 2 Sätze am Stück, dann visueller Wechsel
- Prompts müssen SOFORT kopierbar sein mit [PLATZHALTERN]
- Deutsch, du-Form, direkt und persönlich wie Olga spricht
- Kein generisches KI-Deutsch ("Im heutigen dynamischen..." VERBOTEN)
- Konkret: Beispiele, Zahlen, Copy-Paste-fertig
- KEINE Backticks (```) in JSON-Strings

AUSGABE-FORMAT: Gib NUR gültiges JSON zurück. Kein Markdown, kein Text davor/danach.
Das JSON muss ein Array von Sektionen sein:

[
  {
    "title": "Sektionstitel",
    "blocks": [
      {"type": "text", "content": "Fließtext..."},
      {"type": "subtitle", "content": "Untertitel"},
      {"type": "bullets", "items": ["Punkt 1", "Punkt 2"]},
      {"type": "numbered", "items": ["Schritt 1", "Schritt 2"]},
      {"type": "tip", "content": "Ein hilfreicher Tipp"},
      {"type": "warning", "content": "Wichtiger Hinweis"},
      {"type": "prompt", "content": "Kopierbarer Prompt mit [PLATZHALTER]", "label": "Prompt-Name"},
      {"type": "cards", "items": [{"icon": "🎯", "title": "Titel", "desc": "Beschreibung"}]},
      {"type": "spacer"}
    ]
  }
]"""


def generate_content_with_claude(briefing, title):
    """Nutzt Claude API um aus einem Briefing tiefgehenden Freebie-Inhalt zu erstellen."""
    client = anthropic.Anthropic()  # Nutzt ANTHROPIC_API_KEY aus Environment

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"""Erstelle ein kompaktes, wertvolles Freebie.

TITEL: {title}

BRIEFING:
{briefing}

WICHTIG:
- 3-4 Sektionen, NICHT mehr. Qualität vor Quantität.
- Jede Sektion: 1 kurzer Einleitungssatz, dann sofort Bullets/Prompts/Cards
- Nutze VIELE Cards und Bullets — wenig Fließtext
- Alles muss in 3-5 Minuten lesbar sein
- Jeder Prompt sofort kopierbar mit [PLATZHALTERN]
- Lieber 1 genialer Tipp als 5 mittelmäßige

Antworte NUR mit dem JSON-Array der Sektionen."""
        }]
    )

    # JSON aus Antwort extrahieren
    text = message.content[0].text.strip()
    # Debug: Antwort in Datei loggen
    debug_path = BASE_DIR / "dashboard" / "last_claude_response.txt"
    debug_path.write_text(text, encoding="utf-8")
    print(f"Claude Antwort ({len(text)} Zeichen), gespeichert in {debug_path}")

    # JSON extrahieren — REIHENFOLGE WICHTIG:
    # 1. Wenn es direkt mit [ oder { anfängt → schon JSON, NICHTS tun
    if text.startswith("[") or text.startswith("{"):
        pass  # Bereits JSON
    # 2. Nur wenn es NICHT mit JSON anfängt: Markdown-Block suchen
    elif "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0].strip()
    # 3. Letzter Versuch: Erstes [ ... ] Array finden
    else:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            text = text[start:end + 1]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON Parse Fehler: {e}")
        print(f"Versuche Reparatur...")

        # Repariere abgeschnittenes JSON (wenn max_tokens erreicht)
        # Strategie: Schneide alles nach der letzten vollständigen Sektion ab
        repaired = text
        while True:
            # Finde letzte vollständige } und schließe das Array
            last_complete = repaired.rfind("}")
            if last_complete <= 0:
                break
            repaired = repaired[:last_complete + 1]

            # Schließe offene Arrays/Objekte
            open_brackets = repaired.count("[") - repaired.count("]")
            open_braces = repaired.count("{") - repaired.count("}")
            repaired += "]" * open_brackets

            try:
                result = json.loads(repaired)
                print(f"JSON repariert! {len(result)} Sektionen gerettet.")
                return result
            except json.JSONDecodeError:
                # Nochmal kürzen — eine Ebene weiter zurück
                repaired = repaired[:last_complete]
                continue

        raise e


# ── HTML Builder (identisch mit Vercel-Version) ───────────────

HERO_COLORS = {
    "sky": "linear-gradient(135deg, #6EA8B0 0%, #88BEC5 40%, #A4CCCE 100%)",
    "orange": "linear-gradient(135deg, #DE7C30 0%, #F48225 40%, #f89b4f 100%)",
    "golden": "linear-gradient(135deg, #DE7C30 0%, #EFA818 40%, #f5c44e 100%)",
}


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
    return "".join(
        f'<li><span class="toc-num">{i}</span>'
        f'<a href="#section-{i}">{s["title"]}</a></li>'
        for i, s in enumerate(sections, 1)
    )


def render_tags(tags):
    if not tags:
        tags = ["Sofort einsetzbar", "Praxiserprobt", "Kostenlos"]
    return "".join(f'<span class="hero-tag">{t}</span>' for t in tags)


def build_html(title, description, sections, tags, hero_color):
    hero_bg = HERO_COLORS.get(hero_color, HERO_COLORS["sky"])
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
:root{{--sky:#88BEC5;--sky-light:#A4CCCE;--orange:#F48225;--orange-light:#f89b4f;--golden:#EFA818;--deep-orange:#DE7C30;--navy:#091440;--warm-white:#FFF9ED;--white:#FFFFFF;--text:#091440;--text-light:#3d4f6f;--text-muted:#6b7a94;--border:#e2e8f0}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Inter',-apple-system,sans-serif;background:var(--warm-white);color:var(--text);font-size:16px;line-height:1.7}}
.main{{max-width:780px;margin:0 auto;padding:0 1.5rem;position:relative}}
.main::before{{content:'';position:absolute;top:200px;left:-100px;width:300px;height:300px;background:radial-gradient(circle,rgba(136,190,197,.06),transparent 70%);border-radius:50%;pointer-events:none}}
.main::after{{content:'';position:absolute;top:600px;right:-100px;width:250px;height:250px;background:radial-gradient(circle,rgba(244,130,37,.04),transparent 70%);border-radius:50%;pointer-events:none}}
.hero{{background:{hero_bg};color:var(--white);padding:3rem 1.5rem 4rem;text-align:center;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;top:-50%;right:-20%;width:500px;height:500px;background:radial-gradient(circle,rgba(255,255,255,0.08) 0%,transparent 70%);border-radius:50%}}
.hero-brand{{font-size:.85rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;opacity:.85;margin-bottom:1.5rem}}
.hero-badge{{display:inline-block;background:var(--orange);padding:.35rem 1rem;border-radius:50px;font-size:.75rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;margin-bottom:1.5rem}}
.hero h1{{font-family:'Playfair Display',serif;font-size:clamp(2rem,5vw,3.2rem);font-weight:800;line-height:1.15;margin-bottom:1rem;max-width:700px;margin-left:auto;margin-right:auto}}
.hero-desc{{font-size:1.05rem;opacity:.9;max-width:560px;margin:0 auto 2rem;line-height:1.6}}
.hero-tags{{display:flex;flex-wrap:wrap;justify-content:center;gap:.5rem}}
.hero-tag{{background:rgba(255,255,255,.12);padding:.3rem .9rem;border-radius:8px;font-size:.8rem;font-weight:500}}
.toc{{background:var(--white);border:1px solid var(--border);border-radius:20px;padding:2rem;margin:-2rem auto 3rem;position:relative;z-index:2;box-shadow:0 8px 30px rgba(9,20,64,.08)}}
.toc h2{{font-family:'Playfair Display',serif;font-size:1.2rem;margin-bottom:1rem;color:var(--navy)}}
.toc-list{{list-style:none;display:grid;grid-template-columns:1fr 1fr;gap:.6rem}}
.toc-list li{{display:flex;align-items:center;gap:.6rem}}
.toc-num{{width:28px;height:28px;color:white;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:.75rem;font-weight:700;flex-shrink:0}}
.toc-list li:nth-child(odd) .toc-num{{background:var(--orange)}}
.toc-list li:nth-child(even) .toc-num{{background:var(--sky)}}
.toc-list li:nth-child(3n) .toc-num{{background:var(--navy)}}
.toc-list a{{color:var(--text-light);text-decoration:none;font-size:.9rem;font-weight:500}}
.toc-list a:hover{{color:var(--orange)}}
.section{{margin-bottom:2rem;border-radius:20px;padding:2rem;box-shadow:0 2px 16px rgba(9,20,64,.05)}}
.section:nth-child(odd){{background:var(--white);border:1px solid var(--border)}}
.section:nth-child(even){{background:linear-gradient(135deg,#f0f7f8,#e8f1f2);border:1px solid rgba(136,190,197,.2)}}
.section:nth-child(3n){{background:linear-gradient(135deg,#fff8f0,#fff3e6);border:1px solid rgba(244,130,37,.15)}}
.section-header{{display:flex;align-items:center;gap:.75rem;margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:2px solid rgba(9,20,64,.06)}}
.section-number{{width:42px;height:42px;color:white;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:1rem;font-weight:800;flex-shrink:0}}
.section:nth-child(odd) .section-number{{background:var(--orange);box-shadow:0 3px 12px rgba(244,130,37,.3)}}
.section:nth-child(even) .section-number{{background:var(--sky);box-shadow:0 3px 12px rgba(136,190,197,.3)}}
.section:nth-child(3n) .section-number{{background:var(--navy);box-shadow:0 3px 12px rgba(9,20,64,.2)}}
.section h2{{font-family:'Playfair Display',serif;font-size:1.6rem;font-weight:700;color:var(--navy)}}
.section h3{{font-size:1.05rem;font-weight:700;color:var(--navy);margin:1.8rem 0 .6rem;padding:.7rem 1.1rem;border-radius:10px}}
.section:nth-child(odd) h3{{background:linear-gradient(135deg,#fff5eb,#feecd6);border-left:3px solid var(--orange)}}
.section:nth-child(even) h3{{background:linear-gradient(135deg,#e8f4f5,#d4ecee);border-left:3px solid var(--sky)}}
.section:nth-child(3n) h3{{background:linear-gradient(135deg,#f0f0fa,#e8e8f5);border-left:3px solid var(--navy)}}
.section p{{color:var(--text-light);margin-bottom:1rem}}
.bullet-list{{list-style:none;margin:1rem 0 1.5rem;border-radius:14px;padding:1rem 1.2rem;background:rgba(255,255,255,.7);border:1px solid rgba(9,20,64,.06)}}
.bullet-list li{{display:flex;align-items:flex-start;gap:.75rem;padding:.65rem 0;color:var(--text-light);border-bottom:1px solid rgba(9,20,64,.04)}}
.bullet-list li:last-child{{border-bottom:none}}
.bullet-list li::before{{content:'';width:10px;height:10px;border-radius:50%;flex-shrink:0;margin-top:.4rem}}
.bullet-list li:nth-child(odd)::before{{background:var(--orange);box-shadow:0 0 0 3px rgba(244,130,37,.15)}}
.bullet-list li:nth-child(even)::before{{background:var(--sky);box-shadow:0 0 0 3px rgba(136,190,197,.15)}}
.numbered-list{{list-style:none;counter-reset:step;margin:1rem 0 1.5rem}}
.numbered-list li{{counter-increment:step;display:flex;align-items:flex-start;gap:1rem;padding:.75rem 1rem;color:var(--text-light);background:var(--white);border:1px solid var(--border);border-radius:12px;margin-bottom:.5rem}}
.numbered-list li::before{{content:counter(step);width:32px;height:32px;background:var(--orange);color:white;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:.85rem;font-weight:700;flex-shrink:0;box-shadow:0 3px 10px rgba(244,130,37,.2)}}
.tip-box{{background:linear-gradient(135deg,#e8f4f5,#d4ecee);border:1px solid rgba(136,190,197,.3);border-left:4px solid var(--sky);border-radius:0 14px 14px 0;padding:1.2rem 1.5rem;margin:1.5rem 0;box-shadow:0 2px 8px rgba(136,190,197,.1)}}
.tip-box p{{color:var(--text);margin:0;font-size:.95rem}}
.tip-box strong{{color:#6EA8B0}}
.warning-box{{background:linear-gradient(135deg,#fff5eb,#feecd6);border:1px solid rgba(244,130,37,.2);border-left:4px solid var(--orange);border-radius:0 14px 14px 0;padding:1.2rem 1.5rem;margin:1.5rem 0;box-shadow:0 2px 8px rgba(244,130,37,.08)}}
.warning-box p{{color:var(--text);margin:0;font-size:.95rem}}
.warning-box strong{{color:var(--deep-orange)}}
.prompt-box{{background:var(--white);border:1px solid var(--border);border-radius:14px;overflow:hidden;margin:1.5rem 0;box-shadow:0 2px 12px rgba(9,20,64,.06)}}
.prompt-box-header{{background:linear-gradient(135deg,var(--navy),#1a2a5c);color:var(--white);padding:.7rem 1.2rem;font-size:.75rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;display:flex;align-items:center;justify-content:space-between}}
.prompt-box-header .copy-btn{{background:var(--orange);border:none;color:white;padding:.3rem .9rem;border-radius:8px;font-size:.75rem;cursor:pointer;font-weight:600;transition:all .2s}}
.prompt-box-header .copy-btn:hover{{background:var(--orange-light);transform:translateY(-1px)}}
.prompt-box-content{{padding:1.3rem 1.5rem;font-family:'Courier New',monospace;font-size:.88rem;line-height:1.7;color:var(--text-light);white-space:pre-wrap;background:#fafbfc;border-top:1px solid var(--border)}}
.card-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin:1.5rem 0}}
.card{{background:var(--white);border:1px solid var(--border);border-radius:16px;padding:1.5rem;text-align:center;transition:all .3s;position:relative;overflow:hidden}}
.card::before{{content:'';position:absolute;top:0;left:0;width:100%;height:4px}}
.card:nth-child(1)::before{{background:var(--orange)}}
.card:nth-child(2)::before{{background:var(--sky)}}
.card:nth-child(3)::before{{background:var(--golden)}}
.card:nth-child(4)::before{{background:var(--navy)}}
.card:nth-child(5)::before{{background:var(--deep-orange)}}
.card:nth-child(6)::before{{background:var(--sky)}}
.card:hover{{border-color:var(--sky);transform:translateY(-3px);box-shadow:0 12px 32px rgba(9,20,64,.1)}}
.card-icon{{font-size:2.2rem;margin-bottom:.75rem;filter:drop-shadow(0 2px 4px rgba(0,0,0,.1))}}
.card h4{{font-size:.95rem;font-weight:700;color:var(--navy);margin-bottom:.4rem}}
.card p{{font-size:.82rem;color:var(--text-muted);margin:0;line-height:1.4}}
.divider{{height:1px;background:var(--border);margin:3rem 0}}
.cta-footer{{background:linear-gradient(135deg,var(--sky) 0%,var(--orange) 50%,var(--deep-orange) 100%);color:white;border-radius:20px;padding:3rem 2rem;text-align:center;margin:2rem 0 3rem;position:relative;overflow:hidden}}
.cta-footer::before{{content:'';position:absolute;top:-30%;right:-10%;width:300px;height:300px;background:radial-gradient(circle,rgba(255,255,255,.1),transparent 70%);border-radius:50%}}
.cta-footer h2{{font-family:'Playfair Display',serif;font-size:1.8rem;margin-bottom:1rem}}
.cta-footer p{{color:rgba(255,255,255,.9);margin-bottom:1.5rem;max-width:480px;margin-left:auto;margin-right:auto}}
.cta-links{{display:flex;flex-wrap:wrap;justify-content:center;gap:.75rem}}
.cta-link{{display:inline-flex;align-items:center;gap:.5rem;background:var(--white);color:var(--navy);padding:.85rem 1.8rem;border-radius:12px;font-weight:700;font-size:.95rem;text-decoration:none;transition:all .2s}}
.cta-link:hover{{transform:translateY(-2px);box-shadow:0 6px 20px rgba(0,0,0,.15)}}
.cta-link.secondary{{background:rgba(255,255,255,.15);color:white}}
.cta-link.secondary:hover{{background:rgba(255,255,255,.25)}}
.footer{{text-align:center;padding:2rem 1.5rem;color:var(--text-muted);font-size:.8rem;border-top:1px solid var(--border)}}
.footer a{{color:var(--orange);text-decoration:none}}
@media(max-width:600px){{.hero{{padding:2rem 1rem 3rem}}.toc-list{{grid-template-columns:1fr}}.card-grid{{grid-template-columns:1fr}}.cta-links{{flex-direction:column;align-items:center}}}}
.copy-btn.copied{{background:rgba(136,190,197,.4)!important}}
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
<p style="margin-top:.4rem"><a href="https://www.skool.com/ag3nt-c-2041/about">Community</a> &middot; <a href="https://blotato.com/?ref=olgai3">Blotato</a></p>
</footer>
<script>
document.addEventListener('click',function(e){{if(e.target.classList.contains('copy-btn')){{const box=e.target.closest('.prompt-box');const text=box.querySelector('.prompt-box-content').textContent;navigator.clipboard.writeText(text.trim()).then(()=>{{e.target.textContent='Kopiert!';e.target.classList.add('copied');setTimeout(()=>{{e.target.textContent='Kopieren';e.target.classList.remove('copied')}},2000)}});}}}});
</script>
</body>
</html>'''


# ── Vercel Deploy (reine API, kein CLI) ───────────────────────

def _vercel_api(method, path, payload=None):
    """Zentraler Vercel API-Aufruf."""
    token = os.environ.get("VERCEL_TOKEN", "")
    url = f"https://api.vercel.com{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None

    req = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Vercel API Fehler {e.code}: {body[:300]}")
        raise Exception(f"Vercel API {e.code}: {body[:200]}")


def deploy_to_vercel(name, html_content):
    """Deployed via Vercel API — kein CLI nötig."""
    # Auch lokal speichern
    deploy_dir = BASE_DIR / name
    deploy_dir.mkdir(exist_ok=True)
    (deploy_dir / "index.html").write_text(html_content, encoding="utf-8")
    (deploy_dir / "vercel.json").write_text('{"version": 2}', encoding="utf-8")

    # Via API deployen
    html_b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    result = _vercel_api("POST", "/v13/deployments", {
        "name": name,
        "files": [
            {"file": "index.html", "data": html_b64, "encoding": "base64"}
        ],
        "projectSettings": {"framework": None},
        "target": "production"
    })

    url = f"https://{result.get('url', name + '.vercel.app')}"
    aliases = result.get("alias", [])
    if aliases:
        url = f"https://{aliases[0]}"

    return {
        "success": True,
        "url": url,
        "id": result.get("id", ""),
    }


def update_redirect_file(keyword, freebie_url):
    """Aktualisiert die go/index.html und re-deployed via API."""
    go_dir = BASE_DIR / "go"
    go_html = go_dir / "index.html"

    if not go_html.exists():
        return {"ok": False, "error": "go/index.html nicht gefunden"}

    content = go_html.read_text(encoding="utf-8")
    keyword_upper = keyword.upper()

    if f'"{keyword_upper}"' in content:
        content = re.sub(
            f'"{keyword_upper}":\\s*"[^"]*"',
            f'"{keyword_upper}":  "{freebie_url}"',
            content
        )
    else:
        # Neues Keyword einfügen
        marker = "// Neue Freebies hier einfügen:"
        if marker in content:
            entry = f'            "{keyword_upper}":  "{freebie_url}",\n            {marker}'
            content = content.replace(marker, entry)

    go_html.write_text(content, encoding="utf-8")

    # Re-deploy via API
    try:
        vercel_json = '{"version":2,"builds":[{"src":"index.html","use":"@vercel/static"}],"routes":[{"src":"/(.*)","dest":"/index.html"}]}'
        html_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        vj_b64 = base64.b64encode(vercel_json.encode("utf-8")).decode("ascii")

        _vercel_api("POST", "/v13/deployments", {
            "name": "go",
            "files": [
                {"file": "index.html", "data": html_b64, "encoding": "base64"},
                {"file": "vercel.json", "data": vj_b64, "encoding": "base64"},
            ],
            "projectSettings": {"framework": None},
            "target": "production"
        })
        return {"ok": True}
    except Exception as e:
        print(f"Redirect re-deploy Fehler: {e}")
        return {"ok": False, "error": str(e)}


# ── API Routes ────────────────────────────────────────────────

@app.route("/")
def index():
    return send_file("index.html")


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """Hauptendpoint: Briefing → Claude Content → Deploy → URL."""
    data = request.json or {}

    title = data.get("title", "").strip()
    keyword = data.get("keyword", "FREEBIE").strip().upper()
    description = data.get("description", "").strip()
    briefing = data.get("briefing", "").strip()
    tags = data.get("tags", [])
    hero_color = data.get("heroColor", "sky")
    output_format = data.get("format", "vercel")  # "vercel" oder "pdf"

    if not title:
        return jsonify({"error": "Titel fehlt"}), 400

    # Slug
    name = title.lower()
    for old, new in [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]:
        name = name.replace(old, new)
    name = re.sub(r"[^a-z0-9]+", "-", name).strip("-")

    try:
        # 1. Content mit Claude generieren
        print(f"🧠 Claude generiert Inhalt für: {title}")
        sections = generate_content_with_claude(
            briefing or description or title,
            title
        )
        print(f"✅ {len(sections)} Sektionen generiert")

        freebie_url = ""
        redirect_result = {"ok": False}

        if output_format == "pdf":
            # PDF generieren
            print("📄 Generiere PDF...")
            sys.path.insert(0, str(BASE_DIR))
            from pdf_generator import generate_pdf
            pdf_path = generate_pdf(
                name, title,
                description or briefing or title,
                sections_data=sections,
                output_dir=str(BASE_DIR / name)
            )
            print(f"✅ PDF: {pdf_path}")
        else:
            # 2. HTML bauen
            print("🔨 Baue HTML...")
            html = build_html(title, description or briefing, sections, tags, hero_color)

            # 3. Auf Vercel deployen
            print("🚀 Deploye auf Vercel...")
            deploy_result = deploy_to_vercel(name, html)

            if not deploy_result["success"]:
                return jsonify({"error": f"Deploy fehlgeschlagen"}), 500

            freebie_url = deploy_result["url"]
            print(f"✅ Live: {freebie_url}")

            # 4. Redirect aktualisieren
            print(f"🔄 Aktualisiere Redirect für {keyword}...")
            redirect_result = update_redirect_file(keyword, freebie_url)

        # 5. Sections speichern für späteren Zugriff
        sections_dir = BASE_DIR / "examples"
        sections_dir.mkdir(exist_ok=True)
        (sections_dir / f"{name}-sections.json").write_text(
            json.dumps(sections, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return jsonify({
            "success": True,
            "name": name,
            "title": title,
            "keyword": keyword,
            "format": output_format,
            "freebie_url": freebie_url,
            "redirect_url": f"https://go-bay.vercel.app/go/{keyword}",
            "redirect_updated": redirect_result.get("ok", False),
            "sections_count": len(sections),
        })

    except json.JSONDecodeError as e:
        return jsonify({"error": f"Claude hat kein gueltiges JSON geliefert: {str(e)}"}), 500
    except anthropic.APIError as e:
        return jsonify({"error": f"Claude API Fehler: {str(e)}"}), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/pdf/<name>")
def api_pdf_download(name):
    """PDF-Download Endpoint."""
    pdf_dir = BASE_DIR / name
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if pdf_files:
        return send_file(str(pdf_files[0]), as_attachment=True)
    return jsonify({"error": "PDF nicht gefunden"}), 404


@app.route("/api/freebies", methods=["GET"])
def api_freebies():
    """Listet alle vorhandenen Freebies auf."""
    freebies = []
    for d in sorted(BASE_DIR.iterdir()):
        if d.is_dir() and (d / "index.html").exists() and d.name not in ("dashboard", "go", "examples", "__pycache__", ".git", ".vercel"):
            # Versuche Sections-Datei zu finden für Metadaten
            sections_file = BASE_DIR / "examples" / f"{d.name}-sections.json"
            sections_count = 0
            if sections_file.exists():
                try:
                    sections_count = len(json.loads(sections_file.read_text(encoding="utf-8")))
                except Exception:
                    pass

            freebies.append({
                "name": d.name,
                "title": d.name.replace("-", " ").title(),
                "sections": sections_count,
                "has_html": True,
            })

    return jsonify(freebies)


@app.route("/api/freebies/<name>", methods=["DELETE"])
def api_delete_freebie(name):
    """Löscht ein Freebie (lokaler Ordner)."""
    import shutil
    freebie_dir = BASE_DIR / name

    # Sicherheitscheck
    if name in ("dashboard", "go", "examples", ".git", "__pycache__"):
        return jsonify({"error": "System-Ordner kann nicht gelöscht werden"}), 400

    if not freebie_dir.exists():
        return jsonify({"error": "Freebie nicht gefunden"}), 404

    try:
        shutil.rmtree(str(freebie_dir))

        # Auch sections.json löschen falls vorhanden
        sections_file = BASE_DIR / "examples" / f"{name}-sections.json"
        if sections_file.exists():
            sections_file.unlink()

        print(f"🗑️ Freebie gelöscht: {name}")
        return jsonify({"success": True, "name": name})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Statische Dateien aus Freebie-Ordnern servieren ───────────

@app.route("/<name>/index.html")
def serve_freebie(name):
    """Serviert Freebie-Seiten aus Unterordnern."""
    freebie_dir = BASE_DIR / name
    if (freebie_dir / "index.html").exists():
        return send_file(str(freebie_dir / "index.html"))
    return "Nicht gefunden", 404


# ── Start ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🎯 Freebie Dashboard")
    print("=" * 50)
    print(f"📂 Projektordner: {BASE_DIR}")
    print(f"🌐 Öffne: http://localhost:5000")
    print(f"{'=' * 50}\n")

    app.run(host="0.0.0.0", port=5000, debug=False)
