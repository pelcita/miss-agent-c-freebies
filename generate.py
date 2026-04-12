"""
Freebie-Generator für Miss Agent C.
Erzeugt Landing Page + PDF, pusht zu GitHub, wartet auf Vercel-Deployment.

Hinweis: Auf Windows mit PYTHONIOENCODING=utf-8 ausführen oder
         das Skript setzt es automatisch.

Aufruf:
    python generate.py --name "prompt-bibliothek" --title "Die ultimative Prompt-Bibliothek" --keyword "PROMPT"

Optionen:
    --name        Slug-Name (wird Ordnername + URL-Teil)
    --title       Titel des Freebies
    --keyword     ManyChat-Keyword (z.B. PROMPT, SKILLS)
    --description Kurzbeschreibung für die Landing Page
    --benefits    Komma-getrennte Benefits
    --downloads   Anzahl Downloads (Social Proof)
    --sections    Pfad zu sections.json für PDF-Inhalt
    --skip-push   Nur lokal generieren, nicht pushen
    --skip-pdf    Kein PDF generieren
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

# Fix Windows console encoding für Emoji-Output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import requests

from pdf_generator import generate_pdf


# ── HTML generieren ─────────────────────────────────────────────

DEFAULT_TAGS = ["Sofort einsetzbar", "Praxiserprobt", "Kostenlos"]


def render_block_html(block):
    """Rendert einen einzelnen Content-Block als HTML."""
    block_type = block.get("type", "text")

    if block_type == "text":
        return f'        <p>{block["content"]}</p>'

    elif block_type == "subtitle":
        return f'        <h3>{block["content"]}</h3>'

    elif block_type == "bullets":
        items = "\n".join(f'            <li>{item}</li>' for item in block["items"])
        return f'        <ul class="bullet-list">\n{items}\n        </ul>'

    elif block_type == "numbered":
        items = "\n".join(f'            <li>{item}</li>' for item in block["items"])
        return f'        <ol class="numbered-list">\n{items}\n        </ol>'

    elif block_type == "tip":
        return (
            f'        <div class="tip-box">\n'
            f'            <p><strong>Tipp:</strong> {block["content"]}</p>\n'
            f'        </div>'
        )

    elif block_type == "warning":
        return (
            f'        <div class="warning-box">\n'
            f'            <p><strong>Wichtig:</strong> {block["content"]}</p>\n'
            f'        </div>'
        )

    elif block_type == "prompt":
        label = block.get("label", "Prompt")
        return (
            f'        <div class="prompt-box">\n'
            f'            <div class="prompt-box-header">\n'
            f'                <span>{label}</span>\n'
            f'                <button class="copy-btn">Kopieren</button>\n'
            f'            </div>\n'
            f'            <div class="prompt-box-content">{block["content"]}</div>\n'
            f'        </div>'
        )

    elif block_type == "cards":
        cards_html = ""
        for card in block["items"]:
            icon = card.get("icon", "")
            cards_html += (
                f'            <div class="card">\n'
                f'                <div class="card-icon">{icon}</div>\n'
                f'                <h4>{card["title"]}</h4>\n'
                f'                <p>{card.get("desc", "")}</p>\n'
                f'            </div>\n'
            )
        return f'        <div class="card-grid">\n{cards_html}        </div>'

    elif block_type == "spacer":
        return '        <div class="divider"></div>'

    return ""


def render_sections_html(sections):
    """Rendert alle Sektionen als HTML mit Nummerierung."""
    html_parts = []
    for i, section in enumerate(sections, 1):
        section_id = f"section-{i}"
        blocks_html = "\n".join(render_block_html(b) for b in section.get("blocks", []))
        section_html = (
            f'    <section class="section" id="{section_id}">\n'
            f'        <div class="section-header">\n'
            f'            <div class="section-number">{i}</div>\n'
            f'            <h2>{section["title"]}</h2>\n'
            f'        </div>\n'
            f'{blocks_html}\n'
            f'    </section>'
        )
        html_parts.append(section_html)
    return "\n\n".join(html_parts)


def render_toc_html(sections):
    """Rendert das Inhaltsverzeichnis."""
    items = []
    for i, section in enumerate(sections, 1):
        items.append(
            f'                <li>\n'
            f'                    <span class="toc-num">{i}</span>\n'
            f'                    <a href="#section-{i}">{section["title"]}</a>\n'
            f'                </li>'
        )
    return "\n".join(items)


def render_tags_html(tags=None):
    """Rendert die Tags im Hero."""
    if tags is None:
        tags = DEFAULT_TAGS
    return "\n".join(f'            <span class="hero-tag">{t}</span>' for t in tags)


def generate_html(name, title, keyword, description=None, sections=None,
                  tags=None, **kwargs):
    """Erzeugt die interaktive Freebie-Seite aus dem Template."""
    template_path = os.path.join(os.path.dirname(__file__), "template.html")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    if description is None:
        description = f"Hol dir jetzt kostenlos: {title}. Praxiserprobt, sofort einsetzbar."

    if sections is None:
        sections = []

    html = html.replace("{{TITLE}}", title)
    html = html.replace("{{DESCRIPTION}}", description)
    html = html.replace("{{TAGS}}", render_tags_html(tags))
    html = html.replace("{{TOC}}", render_toc_html(sections))
    html = html.replace("{{SECTIONS}}", render_sections_html(sections))

    return html


def generate_vercel_json(name):
    """Erzeugt eine minimale vercel.json für den Unterordner."""
    return json.dumps({
        "version": 2
    }, indent=2, ensure_ascii=False)


# ── Dateien schreiben ───────────────────────────────────────────

def write_freebie_files(name, title, keyword, description=None,
                        sections_file=None, skip_pdf=False, tags=None, **kwargs):
    """Erzeugt den Freebie-Ordner mit allen Dateien."""
    freebie_dir = os.path.join(os.path.dirname(__file__), name)
    os.makedirs(freebie_dir, exist_ok=True)

    # Sections laden
    sections = []
    if sections_file and os.path.exists(sections_file):
        with open(sections_file, "r", encoding="utf-8") as f:
            sections = json.load(f)

    # HTML
    html = generate_html(name, title, keyword, description, sections=sections, tags=tags)
    html_path = os.path.join(freebie_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML: {html_path}")

    # vercel.json
    vercel_path = os.path.join(freebie_dir, "vercel.json")
    with open(vercel_path, "w", encoding="utf-8") as f:
        f.write(generate_vercel_json(name))
    print(f"✅ vercel.json: {vercel_path}")

    # PDF
    if not skip_pdf:
        subtitle = description or f"Ein Freebie von Miss Agent C"
        pdf_path = generate_pdf(
            name, title, subtitle,
            sections_file=sections_file,
            output_dir=freebie_dir
        )
        print(f"✅ PDF: {pdf_path}")

    # Redirect-Service aktualisieren
    update_redirect_map(name, keyword)

    return freebie_dir


def update_redirect_map(name, keyword):
    """Fügt ein neues Keyword → URL Mapping in go/index.html ein."""
    go_path = os.path.join(os.path.dirname(__file__), "go", "index.html")
    if not os.path.exists(go_path):
        print(f"⚠️  Redirect-Service nicht gefunden: {go_path}")
        return

    with open(go_path, "r", encoding="utf-8") as f:
        content = f.read()

    keyword_upper = keyword.upper()

    # Prüfen ob Keyword schon existiert
    if f'"{keyword_upper}"' in content:
        print(f"✅ Redirect: {keyword_upper} (bereits vorhanden)")
        return

    # Platzhalter-URL — wird nach Vercel-Deploy mit echter URL ersetzt
    entry = f'            "{keyword_upper}":  "https://{name}-DEPLOY-URL.vercel.app",'

    # Vor dem Kommentar "// Neue Freebies hier einfügen:" einfügen
    marker = "            // Neue Freebies hier einfügen:"
    if marker in content:
        content = content.replace(marker, f"{entry}\n{marker}")
    else:
        content = content.replace("        };", f"{entry}\n        }};")

    with open(go_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"⚠️  Redirect: {keyword_upper} eingetragen — URL muss nach Deploy aktualisiert werden")


# ── Git Push ────────────────────────────────────────────────────

def push_to_github(name):
    """Staged, committed und pusht den neuen Freebie-Ordner."""
    base_dir = os.path.dirname(__file__)

    def run_git(*args):
        result = subprocess.run(
            ["git"] + list(args),
            cwd=base_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"⚠️  git {' '.join(args)}: {result.stderr.strip()}")
        return result

    run_git("add", name)
    run_git("commit", "-m", f"Add freebie: {name}")
    result = run_git("push")

    if result.returncode == 0:
        print(f"✅ Pushed to GitHub: {name}")
    else:
        print(f"❌ Push fehlgeschlagen: {result.stderr}")

    return result.returncode == 0


# ── Vercel URL ──────────────────────────────────────────────────

def get_vercel_url(name, max_wait=300, interval=10):
    """
    Pollt die Vercel API bis das Deployment READY ist.
    Gibt die Produktions-URL zurück.
    """
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        url = f"https://{name}-miss-agent-c.vercel.app"
        print(f"⚠️  Kein VERCEL_TOKEN — erwartete URL: {url}")
        return url

    headers = {"Authorization": f"Bearer {token}"}
    team_id = os.environ.get("VERCEL_TEAM_ID", "")
    params = {}
    if team_id:
        params["teamId"] = team_id

    print(f"⏳ Warte auf Vercel-Deployment für '{name}'...")

    for elapsed in range(0, max_wait, interval):
        try:
            resp = requests.get(
                "https://api.vercel.com/v6/deployments",
                headers=headers,
                params={**params, "limit": 5},
                timeout=15
            )
            if resp.status_code == 200:
                for dep in resp.json().get("deployments", []):
                    if name in dep.get("name", "") and dep.get("state") == "READY":
                        url = f"https://{dep['url']}"
                        print(f"✅ Vercel READY: {url}")
                        return url
        except requests.RequestException as e:
            print(f"⚠️  Vercel API Fehler: {e}")

        time.sleep(interval)

    url = f"https://{name}-miss-agent-c.vercel.app"
    print(f"⏱️  Timeout — erwartete URL: {url}")
    return url


# ── ManyChat ────────────────────────────────────────────────────

def update_manychat(keyword, new_url):
    """Aktualisiert den ManyChat-Flow mit der neuen URL."""
    token = os.environ.get("MANYCHAT_TOKEN")
    flow_key = f"MANYCHAT_FLOW_{keyword.upper()}"
    flow_id = os.environ.get(flow_key)

    if not token or not flow_id:
        print(f"⚠️  ManyChat übersprungen (fehlt: {'MANYCHAT_TOKEN' if not token else flow_key})")
        return False

    try:
        resp = requests.post(
            "https://api.manychat.com/fb/sending/sendContent",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"flow_ns": flow_id, "url": new_url},
            timeout=15
        )
        if resp.status_code == 200:
            print(f"✅ ManyChat Flow '{keyword}' aktualisiert mit {new_url}")
            return True
        else:
            print(f"⚠️  ManyChat Fehler: {resp.status_code} — {resp.text[:200]}")
            return False
    except requests.RequestException as e:
        print(f"⚠️  ManyChat Fehler: {e}")
        return False


# ── Telegram ────────────────────────────────────────────────────

def notify_telegram(message):
    """Sendet eine Bestätigung via Telegram."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print(f"⚠️  Telegram übersprungen (Token/Chat-ID fehlt)")
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=15
        )
        if resp.status_code == 200:
            print("✅ Telegram-Benachrichtigung gesendet")
            return True
        else:
            print(f"⚠️  Telegram Fehler: {resp.status_code}")
            return False
    except requests.RequestException as e:
        print(f"⚠️  Telegram Fehler: {e}")
        return False


# ── Hauptprogramm ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Freebie-Generator für Miss Agent C",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--name", required=True, help="Slug-Name (z.B. prompt-bibliothek)")
    parser.add_argument("--title", required=True, help="Titel des Freebies")
    parser.add_argument("--keyword", required=True, help="ManyChat-Keyword (z.B. PROMPT)")
    parser.add_argument("--description", default=None, help="Kurzbeschreibung")
    parser.add_argument("--sections", default=None, help="Pfad zu sections.json")
    parser.add_argument("--skip-push", action="store_true", help="Nicht zu GitHub pushen")
    parser.add_argument("--skip-pdf", action="store_true", help="Kein PDF generieren")
    parser.add_argument("--skip-manychat", action="store_true", help="ManyChat nicht updaten")
    parser.add_argument("--skip-telegram", action="store_true", help="Keine Telegram-Nachricht")

    args = parser.parse_args()

    # Slug normalisieren
    name = re.sub(r"[^a-z0-9-]", "", args.name.lower().replace(" ", "-"))

    print(f"\n{'='*50}")
    print(f"🚀 Freebie-Generator: {args.title}")
    print(f"{'='*50}\n")

    # 1. Dateien generieren
    print("📁 Generiere Dateien...")
    freebie_dir = write_freebie_files(
        name=name,
        title=args.title,
        keyword=args.keyword,
        description=args.description,
        sections_file=args.sections,
        skip_pdf=args.skip_pdf,
    )

    # 2. Git Push
    url = f"https://{name}-miss-agent-c.vercel.app"
    if not args.skip_push:
        print("\n📤 Pushe zu GitHub...")
        push_to_github(name)

        # 3. Vercel URL abwarten
        print("\n🌐 Warte auf Vercel...")
        url = get_vercel_url(name)
    else:
        print("\n⏭️  Git Push übersprungen")

    # 4. ManyChat
    if not args.skip_manychat:
        print("\n🤖 Aktualisiere ManyChat...")
        update_manychat(args.keyword, url)
    else:
        print("\n⏭️  ManyChat übersprungen")

    # 5. Telegram Bestätigung
    if not args.skip_telegram:
        print("\n📱 Sende Telegram-Bestätigung...")
        notify_telegram(
            f"✅ <b>Freebie \"{args.title}\" ist live!</b>\n\n"
            f"🔗 {url}\n"
            f"🤖 ManyChat-Keyword: <code>{args.keyword.upper()}</code>\n"
            f"📁 Ordner: {name}/"
        )

    # Summary
    print(f"\n{'='*50}")
    print(f"✅ FERTIG!")
    print(f"   Ordner:  {freebie_dir}")
    print(f"   URL:     {url}")
    print(f"   Keyword: {args.keyword.upper()}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
