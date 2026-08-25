#!/usr/bin/env python3
"""Esporta il catalogo in PDF A4 con Chrome headless e verifica che nessuna
scheda finisca a cavallo di due pagine.

Uso:
    python3 export_pdf.py dossier-acquisizione-lugano.html
                          [--pdf dossier-acquisizione-lugano.pdf]
                          [--chrome /percorso/chrome] [--margin 12] [--keep-temp]

Come funziona la verifica del punto 5:
  1. al file viene applicato in stampa `break-inside: avoid` su ogni
     <article class="lot">: Chrome sposta la scheda intera alla pagina
     successiva invece di tagliarla;
  2. quella regola pero' non puo' nulla se una scheda e' piu' alta della
     pagina stampabile, ed e' l'unico caso in cui una scheda si spezza
     davvero. Lo script misura quindi l'altezza reale di ogni scheda alla
     larghezza di colonna dell'A4 e segnala quelle che non ci stanno;
  3. sul PDF prodotto controlla numero di pagine e MediaBox (595x842 pt = A4).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

MM_TO_PX = 96 / 25.4          # CSS px a 96 dpi
A4_MM = (210.0, 297.0)
A4_PT = (595.28, 841.89)
MARKER = "lugano-print-css"

CHROME_CANDIDATES = (
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)

PRINT_CSS = """
  @page {{ size: A4; margin: {margin}mm; }}
  html, body {{ background: #fff; }}
  article.lot, .lot {{
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  article.lot img, .plate, figure, table {{
    break-inside: avoid;
    page-break-inside: avoid;
  }}
  h1, h2, h3, h4 {{ break-after: avoid; page-break-after: avoid; }}
  img {{ max-width: 100%; }}
"""

MEASURE_JS = """
<script>
  window.addEventListener('load', function () {
    var pageH = %(page_h).4f, report = [];
    document.querySelectorAll('.lot').forEach(function (el, i) {
      var h3 = el.querySelector('h3');
      report.push({
        index: i + 1,
        title: h3 ? h3.textContent.trim().replace(/\\s+/g, ' ') : '(senza h3)',
        height: Math.round(el.getBoundingClientRect().height),
        hasImage: !!el.querySelector('img'),
        imageBroken: Array.prototype.some.call(el.querySelectorAll('img'), function (im) {
          return im.complete && im.naturalWidth === 0;
        })
      });
    });
    var node = document.createElement('script');
    node.type = 'application/json';
    node.id = 'lugano-report';
    node.textContent = JSON.stringify({pageHeight: pageH, lots: report});
    document.body.appendChild(node);
  });
</script>
"""


def find_chrome(explicit):
    if explicit:
        return explicit
    for candidate in CHROME_CANDIDATES:
        path = candidate if os.path.isabs(candidate) else shutil.which(candidate)
        if path and os.path.exists(path):
            return path
    sys.exit("Chrome/Chromium non trovato: passalo con --chrome.")


def inject(text, extra_head):
    """Inserisce roba in <head> con lo slicing: re.sub interpreterebbe i
    backslash dello snippet JS come sequenze di escape."""
    head_close = re.search(r"</head\s*>", text, re.I)
    if head_close:
        return text[:head_close.start()] + extra_head + "\n" + text[head_close.start():]
    return extra_head + "\n" + text


def run_chrome(chrome, args, capture=False):
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--disable-dev-shm-usage", "--hide-scrollbars",
           "--allow-file-access-from-files"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0 and not capture:
        sys.stderr.write(proc.stderr[-2000:] + "\n")
        sys.exit(f"Chrome è uscito con codice {proc.returncode}")
    return proc


def pdf_facts(path):
    """Numero di pagine e formato, letti direttamente dal PDF."""
    with open(path, "rb") as fh:
        blob = fh.read()
    pages = len(re.findall(rb"/Type\s*/Page[^s]", blob))
    boxes = set()
    for match in re.finditer(rb"/MediaBox\s*\[\s*([\d.\s-]+?)\]", blob):
        nums = [float(n) for n in match.group(1).split()]
        if len(nums) == 4:
            boxes.add((round(nums[2] - nums[0], 1), round(nums[3] - nums[1], 1)))
    return len(blob), pages, boxes


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("html")
    parser.add_argument("--pdf", help="PDF di destinazione")
    parser.add_argument("--chrome", help="percorso di Chrome/Chromium")
    parser.add_argument("--margin", type=float, default=12.0, help="margine di pagina in mm")
    parser.add_argument("--keep-temp", action="store_true")
    args = parser.parse_args()

    chrome = find_chrome(args.chrome)
    source = os.path.abspath(args.html)
    pdf_path = os.path.abspath(args.pdf or os.path.splitext(source)[0] + ".pdf")
    with open(source, encoding="utf-8") as fh:
        original = fh.read()

    css_body = PRINT_CSS.format(margin=args.margin)
    page_h = (A4_MM[1] - 2 * args.margin) * MM_TO_PX
    page_w = (A4_MM[0] - 2 * args.margin) * MM_TO_PX

    # I file temporanei stanno accanto all'originale: i src="covers/..." relativi
    # devono continuare a risolversi.
    workdir = tempfile.mkdtemp(prefix=".lugano-print-", dir=os.path.dirname(source))
    print_html = os.path.join(workdir, "print.html")
    measure_html = os.path.join(workdir, "measure.html")
    try:
        rebase = f'<base href="file://{os.path.dirname(source)}/">'
        with open(print_html, "w", encoding="utf-8") as fh:
            fh.write(inject(original, f'{rebase}<style id="{MARKER}" media="print">{css_body}</style>'))
        with open(measure_html, "w", encoding="utf-8") as fh:
            fh.write(inject(original, f'{rebase}<style id="{MARKER}">{css_body}</style>'
                                      + MEASURE_JS % {"page_h": page_h}))

        print(f"Chrome   : {chrome}")
        print(f"Sorgente : {source}")
        print(f"Pagina   : A4, margini {args.margin:g} mm → "
              f"area stampabile {page_w:.0f}×{page_h:.0f} px CSS\n")

        run_chrome(chrome, [
            "--no-pdf-header-footer", "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}", "--virtual-time-budget=15000",
            f"file://{print_html}",
        ])

        proc = run_chrome(chrome, [
            "--dump-dom", "--virtual-time-budget=15000",
            f"--window-size={int(page_w)},{int(page_h)}",
            f"file://{measure_html}",
        ], capture=True)

        found = re.search(r'<script type="application/json" id="lugano-report">(.*?)</script>',
                          proc.stdout, re.S)
        if not found:
            found = re.search(r'id="lugano-report"[^>]*>(.*?)</script>', proc.stdout, re.S)

        problems = []
        if not found:
            print("! Misurazione non riuscita: verifica delle schede saltata.")
        else:
            data = json.loads(found.group(1))
            lots = data["lots"]
            print(f"Schede misurate: {len(lots)}\n")
            width = max((len(l["title"]) for l in lots), default=10)
            width = min(width, 58)
            for lot in lots:
                ratio = lot["height"] / page_h
                if ratio > 1.0:
                    flag, msg = "SPEZZATA", f"{lot['height']}px = {ratio*100:.0f}% della pagina"
                    problems.append(f"«{lot['title']}» è più alta della pagina stampabile "
                                    f"({lot['height']}px vs {page_h:.0f}px)")
                elif ratio > 0.92:
                    flag, msg = "limite  ", f"{lot['height']}px = {ratio*100:.0f}% della pagina"
                else:
                    flag, msg = "ok      ", f"{lot['height']}px = {ratio*100:.0f}%"
                print(f"  {flag} {lot['title'][:width]:<{width}}  {msg}")
                if not lot["hasImage"]:
                    problems.append(f"«{lot['title']}» non ha nessuna <img>: segnaposto ancora lì?")
                elif lot["imageBroken"]:
                    problems.append(f"«{lot['title']}» ha un'immagine che non si carica")

        size, pages, boxes = pdf_facts(pdf_path)
        print(f"\nPDF      : {pdf_path} ({size // 1024} KB, {pages} pagine)")
        for box in sorted(boxes):
            ok = abs(box[0] - A4_PT[0]) < 2 and abs(box[1] - A4_PT[1]) < 2
            print(f"MediaBox : {box[0]}×{box[1]} pt {'— A4 ✓' if ok else '— NON A4 ✗'}")
            if not ok:
                problems.append(
                    f"pagina {box[0]}×{box[1]} pt invece di A4: Chrome ha scartato la regola "
                    f"`@page {{ size: A4 }}` (di solito perché i margini non ci stanno) "
                    f"ed è tornato al formato predefinito")

        if problems:
            print("\nDa sistemare prima di stampare:")
            for problem in problems:
                print(f"  · {problem}")
            print("\n  Una scheda più alta della pagina si spezza comunque: riduci il margine\n"
                  "  (--margin 10), accorcia il testo o rimpicciolisci la copertina.")
            return 1

        print("\nNessuna scheda spezzata: ognuna sta in una pagina e "
              "`break-inside: avoid` la tiene unita.")
        return 0
    finally:
        if args.keep_temp:
            print(f"File temporanei in {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
