# Miss Agent C — Freebie-Automatisierung

Automatisierte Pipeline: Telegram-Befehl → Landing Page + PDF → GitHub → Vercel → ManyChat → fertig.

## Projektstruktur

```
miss-agent-c-freebies/
├── template.html             ← HTML-Template (Brand-Farben)
├── generate.py               ← Haupt-Skript (HTML + PDF + Push + Deploy)
├── pdf_generator.py          ← PDF-Erstellung mit ReportLab
├── requirements.txt
├── .env.example
├── examples/
│   └── prompt-bibliothek-sections.json
├── prompt-bibliothek/        ← Generiertes Freebie (Beispiel)
│   ├── index.html
│   ├── vercel.json
│   └── prompt-bibliothek.pdf
└── ...weitere Freebies...
```

## Schnellstart

### 1. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 2. Umgebungsvariablen einrichten

```bash
cp .env.example .env
# .env mit deinen echten Tokens befüllen
```

### 3. Freebie generieren (lokal testen)

```bash
python generate.py \
  --name "prompt-bibliothek" \
  --title "Die ultimative Prompt-Bibliothek" \
  --keyword "PROMPT" \
  --description "50+ getestete KI-Prompts für Content, E-Mail & Business." \
  --sections "examples/prompt-bibliothek-sections.json" \
  --skip-push --skip-manychat --skip-telegram
```

### 4. Voller Durchlauf (mit Deploy)

```bash
python generate.py \
  --name "prompt-bibliothek" \
  --title "Die ultimative Prompt-Bibliothek" \
  --keyword "PROMPT"
```

Das Skript:
1. Generiert HTML + PDF im Ordner `prompt-bibliothek/`
2. Pusht zu GitHub
3. Wartet auf Vercel-Deployment
4. Aktualisiert ManyChat-Flow
5. Sendet Telegram-Bestätigung

## Optionen

| Flag | Beschreibung |
|---|---|
| `--name` | Slug-Name (wird Ordner + URL) |
| `--title` | Titel des Freebies |
| `--keyword` | ManyChat-Keyword |
| `--description` | Kurzbeschreibung für Landing Page |
| `--downloads` | Social-Proof-Zahl (Standard: 500) |
| `--sections` | Pfad zu JSON mit PDF-Inhalten |
| `--skip-push` | Nicht zu GitHub pushen |
| `--skip-pdf` | Kein PDF generieren |
| `--skip-manychat` | ManyChat nicht updaten |
| `--skip-telegram` | Keine Telegram-Nachricht |

## PDF sections.json Format

```json
[
  {
    "title": "Sektions-Titel",
    "blocks": [
      {"type": "text", "content": "Normaler Text"},
      {"type": "subtitle", "content": "Untertitel"},
      {"type": "bullets", "items": ["Punkt 1", "Punkt 2"]},
      {"type": "numbered", "items": ["Schritt 1", "Schritt 2"]},
      {"type": "tip", "content": "Ein hilfreicher Tipp"},
      {"type": "prompt", "content": "Ein kopierbarer Prompt"},
      {"type": "spacer"}
    ]
  }
]
```

## Vercel Setup

1. Vercel Hobby Account anlegen (kostenlos)
2. GitHub-Repo verbinden
3. Jeder Unterordner = eigenes Vercel-Projekt
4. Push = automatisches Deployment

## n8n Workflow (optional)

Für den Telegram-Trigger brauchst du in n8n:
1. **Telegram Trigger** — reagiert auf `FREEBIE: name | titel | keyword`
2. **Function Node** — parst die Nachricht
3. **Execute Command** — `python generate.py --name ... --title ...`
4. **HTTP Request** — Vercel-Status pollen
5. **HTTP Request** — ManyChat updaten
6. **Telegram** — Bestätigung senden

## Claude Code Befehl

```
Lies generate.py und template.html.
Baue mir ein neues Freebie mit:
- Name: prompt-bibliothek
- Titel: Die ultimative Prompt-Bibliothek
- Keyword: PROMPT
Generiere HTML + PDF, pushe zu GitHub
und warte auf die Vercel-URL.
```
