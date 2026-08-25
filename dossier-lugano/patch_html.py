#!/usr/bin/env python3
"""Sostituisce il segnaposto <div class="plate"> di ogni <article class="lot">
con la copertina scaricata da Comic Vine.

Uso:
    python3 patch_html.py dossier-acquisizione-lugano.html [--covers covers]
                          [--out FILE] [--dry-run]

Di default riscrive il file in place lasciando una copia .bak accanto.
L'<img> eredita le classi del div sostituito, cosi' le regole CSS esistenti
(ombra, margini, posizione nella colonna) continuano ad applicarsi; un piccolo
blocco <style> aggiunto in <head> fissa max-width 190px e border-radius 3px.

Lo script e' idempotente: rieseguito, aggiorna le immagini gia' inserite
invece di duplicarle.
"""

import argparse
import html as html_mod
import os
import re
import shutil
import sys

from lots import match_lot

MARKER = "lugano-covers-css"

INJECTED_CSS = f"""<style id="{MARKER}">
  /* copertine Comic Vine inserite da patch_html.py */
  img.plate {{
    display: block;
    width: 100%;
    max-width: 190px;
    height: auto;
    border-radius: 3px;
    object-fit: contain;
  }}
</style>"""

ARTICLE_RE = re.compile(r'<article\b[^>]*\bclass\s*=\s*"([^"]*)"[^>]*>', re.I)
H3_RE = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.I | re.S)
PLATE_OPEN_RE = re.compile(r'<div\b[^>]*\bclass\s*=\s*"([^"]*)"[^>]*>', re.I)
PLATE_IMG_RE = re.compile(r'<img\b[^>]*\bclass\s*=\s*"([^"]*)"[^>]*>', re.I)
DIV_TOKEN_RE = re.compile(r"<div\b|</div\s*>", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def has_class(class_attr, name):
    return name in class_attr.split()


def find_with_class(pattern, text, name):
    """Prima occorrenza che ha davvero `name` fra le sue classi.

    Un \bplate\b sull'attributo intero matcherebbe anche "cover-plate-wrap".
    """
    for match in pattern.finditer(text):
        if has_class(match.group(1), name):
            return match
    return None


def end_of_block(text, open_start):
    """Fine del <div> aperto in open_start, contando le annidature."""
    depth = 0
    for token in DIV_TOKEN_RE.finditer(text, open_start):
        if token.group(0).lower().startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return token.end()
    raise ValueError(f"<div class=\"plate\"> non chiuso a partire dal byte {open_start}")


def article_spans(text):
    """(inizio, fine) di ogni <article class=\"...lot...\">, annidamenti inclusi."""
    spans = []
    for match in ARTICLE_RE.finditer(text):
        if not has_class(match.group(1), "lot"):
            continue
        depth = 0
        for token in re.finditer(r"<article\b|</article\s*>", text[match.start():], re.I):
            if token.group(0).lower().startswith("<article"):
                depth += 1
            else:
                depth -= 1
                if depth == 0:
                    spans.append((match.start(), match.start() + token.end()))
                    break
        else:
            raise ValueError(f"<article class=\"lot\"> non chiuso al byte {match.start()}")
    return spans


def plain_text(fragment):
    return html_mod.unescape(TAG_RE.sub(" ", fragment))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("html", help="il catalogo da modificare")
    parser.add_argument("--covers", default="covers", help="cartella delle copertine")
    parser.add_argument("--out", help="scrive qui invece che in place")
    parser.add_argument("--dry-run", action="store_true",
                        help="mostra le sostituzioni senza scrivere nulla")
    args = parser.parse_args()

    with open(args.html, encoding="utf-8") as fh:
        text = fh.read()

    spans = article_spans(text)
    if not spans:
        sys.exit('Nessun <article class="lot"> trovato: e\' il file giusto?')
    print(f'{len(spans)} <article class="lot"> trovati in {args.html}\n')

    out_dir = os.path.dirname(os.path.abspath(args.out or args.html))
    covers_dir = os.path.abspath(args.covers)
    rel_covers = os.path.relpath(covers_dir, out_dir).replace(os.sep, "/")

    edits = []       # (inizio, fine, sostituzione) — applicati a ritroso
    replaced = skipped = 0
    seen = set()

    for start, end in spans:
        block = text[start:end]

        h3 = H3_RE.search(block)
        if not h3:
            print("  ! article senza <h3>, saltato")
            skipped += 1
            continue
        title = " ".join(plain_text(h3.group(1)).split())

        lot = match_lot(title)
        if lot is None:
            print(f"  ! nessun lotto riconosciuto per {title!r} — lasciato invariato")
            skipped += 1
            continue
        if lot.slug in seen:
            print(f"  ! {lot.slug} gia' usato: due article con lo stesso titolo?")
            skipped += 1
            continue
        seen.add(lot.slug)

        cover = os.path.join(covers_dir, f"{lot.slug}.jpg")
        if not os.path.exists(cover):
            print(f"  ! {title}: manca {cover} — segnaposto lasciato al suo posto")
            skipped += 1
            continue

        alt = html_mod.escape(f"Copertina originale — {lot.label}", quote=True)
        src = f"{rel_covers}/{lot.slug}.jpg" if rel_covers != "." else f"{lot.slug}.jpg"

        already = find_with_class(PLATE_IMG_RE, block, "plate")
        plate = find_with_class(PLATE_OPEN_RE, block, "plate")

        if plate:
            classes = plate.group(1)
            plate_end = end_of_block(block, plate.start())
            removed = " ".join(plain_text(block[plate.start():plate_end]).split())
            img = f'<img class="{classes}" src="{src}" alt="{alt}" loading="lazy">'
            edits.append((start + plate.start(), start + plate_end, img))
            print(f"  ✓ Lotto {lot.number:02d} {title}")
            print(f"      segnaposto rimosso: <div class=\"{classes}\">"
                  + (f' con testo "{removed[:70]}…"' if removed else " (vuoto)"))
            print(f"      inserito: {src}")
            replaced += 1
        elif already:
            img = re.sub(r'\bsrc\s*=\s*"[^"]*"', lambda _: f'src="{src}"', already.group(0))
            img = re.sub(r'\balt\s*=\s*"[^"]*"', lambda _: f'alt="{alt}"', img)
            edits.append((start + already.start(), start + already.end(), img))
            print(f"  ↻ Lotto {lot.number:02d} {title}: copertina gia' presente, aggiornata")
            replaced += 1
        else:
            print(f"  ! {title}: nessun div \"plate\" né <img> da aggiornare")
            skipped += 1

    for begin, finish, replacement in sorted(edits, reverse=True):
        text = text[:begin] + replacement + text[finish:]

    if MARKER not in text:
        head_close = re.search(r"</head\s*>", text, re.I)
        if head_close:
            text = text[:head_close.start()] + INJECTED_CSS + "\n" + text[head_close.start():]
        else:
            text = INJECTED_CSS + "\n" + text
        print("\n  + blocco <style> con max-width 190px / border-radius 3px aggiunto in <head>")

    print(f"\nSostituzioni: {replaced} · non toccati: {skipped} · totale lotti: {len(spans)}")

    if args.dry_run:
        print("--dry-run: nessun file scritto.")
        return 0

    target = args.out or args.html
    if not args.out:
        backup = args.html + ".bak"
        shutil.copy2(args.html, backup)
        print(f"Backup   : {backup}")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"Scritto  : {target}")
    return 0 if skipped == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
