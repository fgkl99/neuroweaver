#!/usr/bin/env python3
"""Scarica da Comic Vine le copertine ufficiali dell'edizione USA originale
dei 16 albi del dossier di Lugano.

Uso:
    export COMICVINE_API_KEY=...      # chiave gratuita da comicvine.gamespot.com/api
    python3 fetch_covers.py [--out covers] [--only slug,slug] [--force]

Produce:
    covers/<slug>.jpg           una copertina per lotto
    covers/manifest.json        volume/numero/data di copertina/URL per ogni file
    covers/contact-sheet.html   provino per il controllo a occhio (punto 4)

Ogni albo viene risolto in due passi (volume, poi numero) invece che con una
ricerca libera: e' il modo per non prendere ristampe, edizioni facsimile o
rilanci omonimi. La data di copertina restituita dall'API viene confrontata
con l'anno atteso e ogni scostamento finisce nel report.
"""

import argparse
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from lots import LOTS, BY_SLUG, normalise

API = "https://comicvine.gamespot.com/api"
# Comic Vine rifiuta gli user agent generici: serve identificarsi.
UA = "lugano-dossier-covers/1.0 (personal want-list build script)"
PAUSE = 1.0          # cortesia fra le chiamate (limite: ~200 richieste/ora)
MAX_RETRY = 4


class ApiError(RuntimeError):
    pass


def get_json(path, params, api_key):
    """GET su Comic Vine con backoff esponenziale su rate limit ed errori di rete."""
    query = dict(params, api_key=api_key, format="json")
    url = f"{API}/{path}/?" + urllib.parse.urlencode(query)
    shown = url.replace(api_key, "***")
    delay = 2.0
    for attempt in range(1, MAX_RETRY + 1):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                payload = json.load(resp)
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError) as exc:
            if attempt == MAX_RETRY:
                raise ApiError(f"{shown}: {exc}") from exc
            print(f"    rete: {exc} — ritento fra {delay:.0f}s", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
            continue

        status = payload.get("status_code")
        if status == 1:
            return payload
        # 107 = rate limit, 100 = chiave non valida
        if status == 100:
            raise ApiError("chiave API rifiutata da Comic Vine (status 100)")
        if attempt == MAX_RETRY:
            raise ApiError(f"{shown}: status {status} — {payload.get('error')}")
        print(f"    API status {status} ({payload.get('error')}) — ritento fra {delay:.0f}s",
              file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise ApiError(shown)


def score_volume(vol, probe):
    """Quanto un volume assomiglia a quello cercato. Negativo = da scartare."""
    name = normalise(vol.get("name") or "")
    want = normalise(probe.volume_query)
    score = 0

    if name == want:
        score += 100
    elif name.startswith(want) or want in name:
        score += 30
    else:
        score -= 40

    start = vol.get("start_year")
    try:
        start = int(start)
    except (TypeError, ValueError):
        start = None
    # L'anno di inizio pesa piu' del nome: i rilanci si chiamano identici
    # all'originale, ed e' l'anno l'unica cosa che li distingue davvero.
    if start == probe.volume_start_year:
        score += 90
    elif start is not None and abs(start - probe.volume_start_year) <= 1:
        score += 35
    elif start is not None:
        score -= 70

    publisher = normalise((vol.get("publisher") or {}).get("name") or "")
    if publisher and any(p in publisher for p in probe.publishers):
        score += 30
    elif publisher:
        score -= 30

    # Un volume troppo corto per contenere il numero cercato e' quasi sempre
    # una raccolta o una ristampa: va escluso, non solo penalizzato.
    count = vol.get("count_of_issues") or 0
    if count and count < probe.min_issue_count:
        score -= 200

    return score


def find_volume(probe, api_key):
    payload = get_json("volumes", {
        "filter": f"name:{probe.volume_query}",
        "field_list": "id,name,start_year,count_of_issues,publisher,site_detail_url",
        "limit": "100",
    }, api_key)
    time.sleep(PAUSE)

    ranked = sorted(
        ((score_volume(v, probe), v) for v in payload.get("results") or []),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not ranked or ranked[0][0] <= 0:
        return None, ranked[:3]
    return ranked[0][1], ranked[:3]


def find_issue(volume_id, issue_number, api_key):
    payload = get_json("issues", {
        "filter": f"volume:{volume_id},issue_number:{issue_number}",
        "field_list": "id,name,issue_number,cover_date,store_date,image,site_detail_url,volume",
        "limit": "10",
    }, api_key)
    time.sleep(PAUSE)
    results = payload.get("results") or []
    return results[0] if results else None


def pick_image_url(image):
    """Preferisce la scansione piu' grande: a 190px di larghezza in stampa
    servono comunque parecchi pixel per non sgranare."""
    for key in ("original_url", "super_url", "screen_large_url", "medium_url"):
        url = (image or {}).get(key)
        if url and not url.endswith("blank.png"):
            return url
    return None


def download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    delay = 2.0
    for attempt in range(1, MAX_RETRY + 1):
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                blob = resp.read()
            break
        except (urllib.error.URLError, TimeoutError, ssl.SSLError) as exc:
            if attempt == MAX_RETRY:
                raise ApiError(f"download {url}: {exc}") from exc
            print(f"    download fallito ({exc}) — ritento fra {delay:.0f}s", file=sys.stderr)
            time.sleep(delay)
            delay *= 2
    if len(blob) < 4096:
        raise ApiError(f"{url}: risposta di soli {len(blob)} byte, non e' una copertina")
    with open(dest, "wb") as fh:
        fh.write(blob)
    return len(blob), hashlib.sha256(blob).hexdigest()


def cover_year(issue):
    for key in ("cover_date", "store_date"):
        value = issue.get(key)
        if value:
            try:
                return int(str(value)[:4]), key
            except ValueError:
                pass
    return None, None


def resolve(lot, api_key):
    """Prova le locazioni note del lotto finche' una restituisce un'immagine."""
    problems = []
    for probe in lot.probes:
        print(f"    volume: {probe.volume_query!r} ({probe.volume_start_year}) #{probe.issue_number}")
        volume, ranked = find_volume(probe, api_key)
        if volume is None:
            near = ", ".join(f"{v.get('name')} ({v.get('start_year')})" for _, v in ranked)
            problems.append(f"nessun volume plausibile per {probe.volume_query!r}"
                            + (f"; piu' vicini: {near}" if near else ""))
            continue
        issue = find_issue(volume["id"], probe.issue_number, api_key)
        if issue is None:
            problems.append(f"{volume['name']} ({volume.get('start_year')}) "
                            f"non ha il numero {probe.issue_number}")
            continue
        url = pick_image_url(issue.get("image"))
        if url is None:
            problems.append(f"{volume['name']} #{probe.issue_number}: nessuna immagine su Comic Vine")
            continue
        return volume, issue, url, problems
    return None, None, None, problems


def build_contact_sheet(records, out_dir):
    """Provino di controllo: le 16 copertine accanto a cio' che dovevano essere."""
    cards = []
    for rec in records:
        klass = "ok" if rec["status"] == "ok" else "warn"
        img = (f'<img src="{rec["file"]}" alt="{rec["label"]}">'
               if rec.get("file") else '<div class="missing">nessuna copertina</div>')
        detail = rec.get("detail", "")
        link = (f'<a href="{rec["site_detail_url"]}">scheda Comic Vine</a>'
                if rec.get("site_detail_url") else "")
        cards.append(f"""  <figure class="{klass}">
    {img}
    <figcaption>
      <b>Lotto {rec['number']:02d} — {rec['label']}</b>
      <span>{detail}</span>
      {link}
    </figcaption>
  </figure>""")

    html = """<meta charset="utf-8">
<title>Provino copertine — Dossier Lugano</title>
<style>
  body{font:14px/1.45 system-ui,sans-serif;margin:24px;background:#f6f5f2;color:#1a1a1a}
  h1{font-size:20px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:20px}
  figure{margin:0;background:#fff;padding:12px;border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.18)}
  figure.warn{outline:2px solid #c8102e}
  img{display:block;width:100%;height:auto;border-radius:3px}
  figcaption{margin-top:8px;font-size:12px}
  figcaption b{display:block}
  figcaption span{display:block;color:#555;margin:2px 0}
  .missing{height:240px;display:grid;place-items:center;background:#eee;color:#888;border-radius:3px}
</style>
<h1>Provino copertine — controllo numero ed edizione</h1>
<p>Ogni riquadro con bordo rosso richiede una verifica manuale.</p>
<div class="grid">
""" + "\n".join(cards) + "\n</div>\n"

    path = os.path.join(out_dir, "contact-sheet.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="covers", help="cartella di destinazione")
    parser.add_argument("--only", help="elenco di slug separati da virgola")
    parser.add_argument("--force", action="store_true", help="riscarica anche i file gia' presenti")
    args = parser.parse_args()

    api_key = os.environ.get("COMICVINE_API_KEY", "").strip()
    if not api_key:
        sys.exit("Manca COMICVINE_API_KEY. Registrala gratis su "
                 "https://comicvine.gamespot.com/api/ ed esportala nell'ambiente.")

    selected = LOTS
    if args.only:
        wanted = [s.strip() for s in args.only.split(",") if s.strip()]
        unknown = [s for s in wanted if s not in BY_SLUG]
        if unknown:
            sys.exit(f"slug sconosciuti: {unknown}")
        selected = tuple(BY_SLUG[s] for s in wanted)

    os.makedirs(args.out, exist_ok=True)
    records = []

    for lot in selected:
        print(f"[{lot.number:02d}/16] {lot.label}")
        dest = os.path.join(args.out, f"{lot.slug}.jpg")
        rec = {"number": lot.number, "slug": lot.slug, "label": lot.label,
               "expect_cover_year": lot.expect_cover_year, "note": lot.note}

        if os.path.exists(dest) and not args.force:
            print("    gia' presente, salto (--force per riscaricare)")
            rec.update(status="skipped", file=os.path.basename(dest),
                       detail="file gia' presente, non riscaricato")
            records.append(rec)
            continue

        try:
            volume, issue, url, problems = resolve(lot, api_key)
        except ApiError as exc:
            print(f"    ERRORE: {exc}", file=sys.stderr)
            rec.update(status="error", detail=str(exc))
            records.append(rec)
            continue

        if issue is None:
            detail = "; ".join(problems) or "non trovato"
            print(f"    NON TROVATO: {detail}", file=sys.stderr)
            rec.update(status="missing", detail=detail)
            records.append(rec)
            continue

        year, year_source = cover_year(issue)
        warnings = []
        if year is None:
            warnings.append("Comic Vine non riporta la data di copertina")
        elif year != lot.expect_cover_year:
            delta = abs(year - lot.expect_cover_year)
            msg = (f"anno {year} ({year_source}) invece di {lot.expect_cover_year} atteso")
            warnings.append(msg if delta > 1 else msg + " — scarto di un anno, plausibile")

        try:
            size, digest = download(url, dest)
        except ApiError as exc:
            print(f"    ERRORE: {exc}", file=sys.stderr)
            rec.update(status="error", detail=str(exc))
            records.append(rec)
            continue

        detail = (f"{volume['name']} ({volume.get('start_year')}) "
                  f"#{issue.get('issue_number')} · copertina {issue.get('cover_date') or '?'}")
        if warnings:
            detail += " · " + " · ".join(warnings)
        hard_warning = any("plausibile" not in w for w in warnings)

        rec.update(
            status="warn" if hard_warning else "ok",
            file=os.path.basename(dest),
            detail=detail,
            volume={"id": volume["id"], "name": volume["name"],
                    "start_year": volume.get("start_year")},
            issue_id=issue["id"],
            issue_number=issue.get("issue_number"),
            cover_date=issue.get("cover_date"),
            store_date=issue.get("store_date"),
            site_detail_url=issue.get("site_detail_url"),
            image_url=url,
            bytes=size,
            sha256=digest,
        )
        records.append(rec)
        print(f"    {'ATTENZIONE' if hard_warning else 'ok'}: {detail} → {dest} ({size//1024} KB)")

    manifest = os.path.join(args.out, "manifest.json")
    with open(manifest, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    sheet = build_contact_sheet(records, args.out)

    tally = {}
    for rec in records:
        tally[rec["status"]] = tally.get(rec["status"], 0) + 1
    print("\nRiepilogo: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))
    print(f"Manifest : {manifest}")
    print(f"Provino  : {sheet}  ← apri questo per il controllo a occhio")

    return 0 if tally.get("ok", 0) + tally.get("skipped", 0) == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
