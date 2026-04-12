"""
PDF-Generator für Miss Agent C Freebies.
Erzeugt professionelle PDF-Freebies mit Brand-Farben.

Aufruf:
    python pdf_generator.py --name "prompt-bibliothek" --title "Die ultimative Prompt-Bibliothek" --sections sections.json
"""

import argparse
import json
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# Brand-Farben (Miss Agent C Brand Guide 2026)
PRIMARY = HexColor("#88BEC5")       # Sky Blue — Hauptfarbe 1
PRIMARY_LIGHT = HexColor("#A4CCCE") # Soft Blue
ACCENT = HexColor("#F48225")        # Accent Orange — Hauptfarbe 2
GOLDEN = HexColor("#EFA818")        # Golden — Akzent
DEEP_ORANGE = HexColor("#DE7C30")   # Deep Orange — Sekundär
NAVY = HexColor("#091440")          # Navy Blue — Headlines, Buttons, Schrift
WARM_WHITE = HexColor("#FFF9ED")    # Warm White — PDF-Hintergrund (IMMER)
BG_CARD = HexColor("#FFFFFF")       # White
TEXT_MUTED = HexColor("#888888")
WHITE = HexColor("#FFFFFF")
DARK_TEXT = HexColor("#091440")     # Navy als Haupttextfarbe

# Pflicht-Links (müssen in jedem PDF enthalten sein)
COMMUNITY_URL = "https://www.skool.com/ag3nt-c-2041/about"
AFFILIATE_URL = "https://blotato.com/?ref=olgai3"


def get_styles():
    """Erstellt alle Paragraph-Styles für das PDF."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=34,
        textColor=NAVY,
        alignment=TA_CENTER,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="CoverSubtitle",
        fontName="Helvetica",
        fontSize=14,
        leading=20,
        textColor=TEXT_MUTED,
        alignment=TA_CENTER,
        spaceAfter=30,
    ))

    styles.add(ParagraphStyle(
        name="SectionTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=26,
        textColor=NAVY,
        spaceBefore=20,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="SubTitle",
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=DARK_TEXT,
        spaceBefore=14,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="BodyText2",
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=DARK_TEXT,
        spaceAfter=8,
    ))

    styles.add(ParagraphStyle(
        name="BulletItem",
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=DARK_TEXT,
        leftIndent=20,
        spaceAfter=4,
        bulletIndent=8,
    ))

    styles.add(ParagraphStyle(
        name="TipBox",
        fontName="Helvetica",
        fontSize=10,
        leading=15,
        textColor=DARK_TEXT,
        backColor=HexColor("#E8F4F5"),
        borderPadding=(10, 12, 10, 12),
        spaceBefore=10,
        spaceAfter=10,
    ))

    styles.add(ParagraphStyle(
        name="FooterText",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=TEXT_MUTED,
        alignment=TA_CENTER,
    ))

    return styles


def build_cover_page(title, subtitle, styles):
    """Erstellt die Titelseite."""
    elements = []
    elements.append(Spacer(1, 60 * mm))

    # Branding-Linie oben
    elements.append(HRFlowable(
        width="40%", thickness=3, color=PRIMARY,
        spaceAfter=20, hAlign="CENTER"
    ))

    elements.append(Paragraph(title, styles["CoverTitle"]))
    elements.append(Paragraph(subtitle, styles["CoverSubtitle"]))

    # Branding
    elements.append(Spacer(1, 40 * mm))
    elements.append(HRFlowable(
        width="30%", thickness=1, color=ACCENT,
        spaceAfter=12, hAlign="CENTER"
    ))
    elements.append(Paragraph(
        "Miss Agent C | @miss.agent.c",
        styles["FooterText"]
    ))
    elements.append(Paragraph(
        "Dein Guide zu KI &amp; Automatisierung",
        styles["FooterText"]
    ))

    elements.append(PageBreak())
    return elements


def build_section(section, styles):
    """Baut eine Sektion aus dem JSON-Format."""
    elements = []

    # Section Title
    elements.append(Paragraph(section["title"], styles["SectionTitle"]))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=HexColor("#E2E8F0"),
        spaceAfter=12
    ))

    for block in section.get("blocks", []):
        block_type = block.get("type", "text")

        if block_type == "text":
            elements.append(Paragraph(block["content"], styles["BodyText2"]))

        elif block_type == "subtitle":
            elements.append(Paragraph(block["content"], styles["SubTitle"]))

        elif block_type == "bullets":
            for item in block["items"]:
                bullet_text = f"\u2022  {item}"
                elements.append(Paragraph(bullet_text, styles["BulletItem"]))
            elements.append(Spacer(1, 4 * mm))

        elif block_type == "numbered":
            for i, item in enumerate(block["items"], 1):
                num_text = f"<b>{i}.</b>  {item}"
                elements.append(Paragraph(num_text, styles["BulletItem"]))
            elements.append(Spacer(1, 4 * mm))

        elif block_type == "tip":
            tip_text = f"\U0001f4a1 <b>Tipp:</b> {block['content']}"
            elements.append(Paragraph(tip_text, styles["TipBox"]))

        elif block_type == "prompt":
            # Prompt-Box mit Hintergrund
            prompt_data = [[Paragraph(
                f"<i>{block['content']}</i>",
                ParagraphStyle(
                    "PromptInner", fontName="Courier", fontSize=10,
                    leading=14, textColor=DARK_TEXT
                )
            )]]
            prompt_table = Table(prompt_data, colWidths=[450])
            prompt_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFF5EB")),
                ("BOX", (0, 0), (-1, -1), 1, ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]))
            elements.append(Spacer(1, 3 * mm))
            elements.append(prompt_table)
            elements.append(Spacer(1, 3 * mm))

        elif block_type == "spacer":
            elements.append(Spacer(1, 8 * mm))

    return elements


def build_cta_page(styles):
    """Erstellt die letzte Seite mit CTA + Pflicht-Links."""
    elements = []
    elements.append(PageBreak())
    elements.append(Spacer(1, 40 * mm))

    elements.append(Paragraph(
        "Hat dir dieses Freebie geholfen?",
        styles["CoverTitle"]
    ))
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "Folge <b>@miss.agent.c</b> auf Instagram<br/>"
        "f\u00fcr mehr KI-Tipps, Prompts &amp; Automatisierungen.",
        ParagraphStyle(
            "CTABody", fontName="Helvetica", fontSize=13,
            leading=20, textColor=DARK_TEXT, alignment=TA_CENTER
        )
    ))
    elements.append(Spacer(1, 12 * mm))
    elements.append(HRFlowable(
        width="30%", thickness=2, color=ACCENT,
        spaceAfter=12, hAlign="CENTER"
    ))
    elements.append(Paragraph(
        "Schreib mir <b>FREEBIE</b> als DM f\u00fcr das n\u00e4chste kostenlose Template!",
        ParagraphStyle(
            "CTAKeyword", fontName="Helvetica-Bold", fontSize=12,
            leading=16, textColor=ACCENT, alignment=TA_CENTER
        )
    ))

    # Pflicht-Links
    elements.append(Spacer(1, 20 * mm))
    elements.append(HRFlowable(
        width="60%", thickness=1, color=PRIMARY_LIGHT,
        spaceAfter=12, hAlign="CENTER"
    ))
    link_style = ParagraphStyle(
        "LinkText", fontName="Helvetica", fontSize=10,
        leading=16, textColor=DARK_TEXT, alignment=TA_CENTER
    )
    elements.append(Paragraph(
        f'Community: <a href="{COMMUNITY_URL}" color="#F48225">skool.com/ag3nt-c-2041/about</a>',
        link_style
    ))
    elements.append(Paragraph(
        f'Tool-Empfehlung: <a href="{AFFILIATE_URL}" color="#F48225">blotato.com/?ref=olgai3</a>',
        link_style
    ))
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "Head Up High GmbH &middot; Olga Reyes-Busch &middot; @miss.agent.c",
        styles["FooterText"]
    ))

    return elements


def add_page_footer(canvas, doc):
    """F\u00fcgt Seitenzahl und Branding in den Footer ein."""
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawCentredString(
        A4[0] / 2, 15 * mm,
        f"@miss.agent.c  |  Seite {doc.page}"
    )
    # Sky Blue Linie oben
    canvas.setStrokeColor(PRIMARY)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, A4[1] - 15 * mm, A4[0] - 20 * mm, A4[1] - 15 * mm)
    canvas.restoreState()


def generate_pdf(name, title, subtitle, sections_file=None, sections_data=None, output_dir="."):
    """
    Generiert das PDF-Freebie.

    Args:
        name: Slug-Name des Freebies (z.B. "prompt-bibliothek")
        title: Titel des Freebies
        subtitle: Untertitel/Beschreibung
        sections_file: Pfad zu JSON-Datei mit Sektionen
        sections_data: Alternativ: Sektionen direkt als Liste
        output_dir: Ausgabeordner
    """
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{name}.pdf")

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = get_styles()
    elements = []

    # Cover
    elements.extend(build_cover_page(title, subtitle, styles))

    # Sections
    if sections_file and os.path.exists(sections_file):
        with open(sections_file, "r", encoding="utf-8") as f:
            sections = json.load(f)
    elif sections_data:
        sections = sections_data
    else:
        sections = get_default_sections(title)

    for section in sections:
        elements.extend(build_section(section, styles))

    # CTA Page
    elements.extend(build_cta_page(styles))

    # Build
    doc.build(elements, onFirstPage=add_page_footer, onLaterPages=add_page_footer)
    print(f"PDF generiert: {output_path}")
    return output_path


def get_default_sections(title):
    """Fallback-Sektionen wenn keine JSON-Datei angegeben."""
    return [
        {
            "title": f"Willkommen zu: {title}",
            "blocks": [
                {"type": "text", "content": "Dieses Freebie wurde erstellt von Miss Agent C."},
                {"type": "text", "content": "Auf den folgenden Seiten findest du praxiserprobte Inhalte, die du sofort umsetzen kannst."},
                {"type": "tip", "content": "Speichere dieses PDF ab und komm immer wieder darauf zur\u00fcck!"},
            ]
        }
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF-Generator f\u00fcr Miss Agent C Freebies")
    parser.add_argument("--name", required=True, help="Slug-Name (z.B. prompt-bibliothek)")
    parser.add_argument("--title", required=True, help="Titel des Freebies")
    parser.add_argument("--subtitle", default="Ein Freebie von Miss Agent C", help="Untertitel")
    parser.add_argument("--sections", default=None, help="Pfad zu sections.json")
    parser.add_argument("--output", default=".", help="Ausgabeordner")

    args = parser.parse_args()
    generate_pdf(args.name, args.title, args.subtitle, sections_file=args.sections, output_dir=args.output)
