#!/usr/bin/env bash
# Catena completa: copertine → catalogo → PDF A4.
#
#   export COMICVINE_API_KEY=...
#   ./run_all.sh /percorso/dossier-acquisizione-lugano.html
#
# Si ferma al primo passo che segnala un problema, cosi' non si stampa un PDF
# con una copertina sbagliata o un segnaposto rimasto indietro.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML="${1:-}"

if [[ -z "$HTML" ]]; then
  echo "uso: $0 /percorso/dossier-acquisizione-lugano.html" >&2
  exit 2
fi
if [[ ! -f "$HTML" ]]; then
  echo "file non trovato: $HTML" >&2
  exit 2
fi
if [[ -z "${COMICVINE_API_KEY:-}" ]]; then
  echo "manca COMICVINE_API_KEY (chiave gratuita su comicvine.gamespot.com/api)" >&2
  exit 2
fi

COVERS="$(cd "$(dirname "$HTML")" && pwd)/covers"

echo "== 1/3 copertine =="
python3 "$HERE/fetch_covers.py" --out "$COVERS"

echo
echo "== 2/3 catalogo =="
python3 "$HERE/patch_html.py" "$HTML" --covers "$COVERS"

echo
echo "== 3/3 PDF A4 =="
python3 "$HERE/export_pdf.py" "$HTML"

echo
echo "Fatto. Prima di stampare apri $COVERS/contact-sheet.html"
echo "e controlla che ogni copertina sia il numero giusto."
