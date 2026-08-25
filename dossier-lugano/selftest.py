#!/usr/bin/env python3
"""Prova la catena patch_html → export_pdf su un dossier sintetico.

Non tocca Comic Vine: costruisce un catalogo con la stessa struttura descritta
(16 <article class="lot"> con <h3> e segnaposto <div class="plate">) e sedici
copertine finte, poi verifica che le sostituzioni e il PDF A4 vengano
corretti. Serve a validare gli script quando la rete non e' disponibile.

    python3 selftest.py [--keep]
"""

import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from lots import LOTS  # noqa: E402

TITLES = [
    "New Mutants #18 — «Death-Hunt»",
    "New Mutants #26 — prima apparizione di Legion",
    "Elektra: Assassin",
    "Daredevil: Love and War",
    "Silver Surfer: Parable",
    "Silver Surfer: Requiem",
    "Fantastic Four: 1234",
    "Marvels",
    "Weapon X",
    "Moonshadow",
    "Uncanny X-Men #221 — prima apparizione di Mister Sinister",
    "Uncanny X-Men #168 — prima apparizione di Madelyne Pryor",
    "Uncanny X-Men #266 — prima apparizione di Gambit",
    "Marvel Super Heroes Secret Wars #1–12",
    "One World Under Doom",
    "Incursions #1–5",
]

CSS = """
  body { font: 15px/1.5 Georgia, serif; margin: 0; color: #17161a; background: #fbfaf7; }
  main { max-width: 760px; margin: 0 auto; padding: 24px; }
  article.lot { display: grid; grid-template-columns: 190px 1fr; gap: 22px;
                margin: 0 0 26px; padding: 18px; background: #fff;
                border: 1px solid #e5e1d8; }
  .plate { max-width: 190px; border-radius: 3px;
           box-shadow: 0 4px 14px rgba(0,0,0,.28); background: #2b2b33;
           color: #cfc7b8; aspect-ratio: 2/3; display: grid; place-items: center;
           text-align: center; font-size: 12px; padding: 8px; }
  h3 { margin: 0 0 4px; font-size: 19px; }
  .credits { color: #6b6559; font-size: 13px; margin: 0 0 10px; }
"""


def png(path, width, height, rgb):
    """Un PNG minimo, sufficiente perche' Chrome lo decodifichi."""
    row = b"\x00" + bytes(rgb) * width
    raw = row * height

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    blob = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6))
            + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(blob)


def build_fixture(root):
    covers = os.path.join(root, "covers")
    os.makedirs(covers, exist_ok=True)
    for i, lot in enumerate(LOTS):
        shade = (40 + (i * 13) % 180, 30 + (i * 29) % 170, 60 + (i * 47) % 160)
        png(os.path.join(covers, f"{lot.slug}.jpg"), 400, 600, shade)

    articles = []
    for title, lot in zip(TITLES, LOTS):
        articles.append(f"""  <article class="lot">
    <div class="plate">Tavola cromatica<br>{lot.label}</div>
    <div class="body">
      <h3>{title}</h3>
      <p class="credits">Marvel · scheda di prova</p>
      <p>Testo di riempimento per dare alla scheda un'altezza realistica.
      {'Trama, contesto critico e nota di mercato. ' * 6}</p>
    </div>
  </article>""")

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>Dossier d'acquisizione · Lugano (fixture)</title>
<style>{CSS}</style>
</head>
<body>
<main>
<h1>Dossier d'acquisizione — fixture di prova</h1>
{chr(10).join(articles)}
</main>
</body>
</html>
"""
    path = os.path.join(root, "dossier-acquisizione-lugano.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path, covers


def run(cmd, cwd):
    print(f"\n$ {' '.join(os.path.basename(c) if c.endswith('.py') else c for c in cmd)}")
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    sys.stdout.write(proc.stdout)
    if proc.stderr.strip():
        sys.stderr.write(proc.stderr)
    return proc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep", action="store_true", help="non cancellare la cartella di prova")
    args = parser.parse_args()

    root = tempfile.mkdtemp(prefix="lugano-selftest-")
    failures = []
    try:
        html, covers = build_fixture(root)
        print(f"Fixture in {root}")

        proc = run([sys.executable, os.path.join(HERE, "patch_html.py"), html,
                    "--covers", covers], HERE)
        if proc.returncode != 0:
            failures.append("patch_html.py è uscito con errore")

        patched = open(html, encoding="utf-8").read()
        imgs = re.findall(r'<img[^>]+class="[^"]*\bplate\b[^"]*"[^>]*>', patched)
        if len(imgs) != 16:
            failures.append(f"attese 16 <img class=\"plate\">, trovate {len(imgs)}")
        if re.search(r'<div[^>]+class="[^"]*\bplate\b', patched):
            failures.append("è rimasto un div segnaposto")
        for lot in LOTS:
            if f"{lot.slug}.jpg" not in patched:
                failures.append(f"{lot.slug}.jpg non referenziato nel file finale")
        if "max-width: 190px" not in patched or "border-radius: 3px" not in patched:
            failures.append("il blocco <style> iniettato non contiene le misure richieste")

        # Rieseguito, non deve duplicare nulla.
        run([sys.executable, os.path.join(HERE, "patch_html.py"), html, "--covers", covers], HERE)
        again = open(html, encoding="utf-8").read()
        if len(re.findall(r'<img[^>]+class="[^"]*\bplate\b[^"]*"[^>]*>', again)) != 16:
            failures.append("la seconda esecuzione ha duplicato le immagini (non idempotente)")
        if again.count('id="lugano-covers-css"') != 1:
            failures.append("il blocco <style> è stato iniettato due volte")

        proc = run([sys.executable, os.path.join(HERE, "export_pdf.py"), html], HERE)
        pdf = os.path.splitext(html)[0] + ".pdf"
        if not os.path.exists(pdf):
            failures.append("il PDF non è stato prodotto")
        elif proc.returncode != 0:
            failures.append("export_pdf.py ha segnalato schede spezzate sulla fixture")

        print("\n" + "=" * 60)
        if failures:
            print("SELFTEST FALLITO:")
            for failure in failures:
                print(f"  · {failure}")
            return 1
        print("SELFTEST OK — patch, idempotenza, PDF A4 e verifica schede.")
        return 0
    finally:
        if args.keep:
            print(f"\nCartella di prova conservata: {root}")
        else:
            import shutil
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
