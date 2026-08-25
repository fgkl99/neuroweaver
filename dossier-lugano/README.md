# Copertine per il dossier d'acquisizione di Lugano

Catena di script che prende il catalogo `dossier-acquisizione-lugano.html`
(16 albi Marvel in altrettanti `<article class="lot">`), scarica da Comic Vine
la copertina dell'edizione USA originale di ognuno, sostituisce i segnaposto
`<div class="plate">` con le immagini e stampa il tutto in PDF A4 senza
schede spezzate a metà.

Le immagini restano in locale, per uso personale come lista d'acquisto: sono
materiale protetto da copyright Marvel e Comic Vine ne consente l'uso
attraverso l'API, non la ripubblicazione. Per questo `covers/` è in
`.gitignore` e non viene versionata.

## Stato: cosa manca per eseguirla

Gli script sono completi e testati, ma **non sono ancora stati eseguiti sul
catalogo vero**, per due motivi indipendenti dal codice:

1. **`comicvine.gamespot.com` non è raggiungibile** dall'ambiente in cui sono
   stati scritti: la policy di rete della sessione risponde `403` al CONNECT
   (l'elenco consentito è di fatto GitHub più i registri dei pacchetti). Non
   è quindi stato possibile né registrare la chiave API né scaricare una sola
   immagine. Vanno eseguiti da una macchina con rete aperta.
2. **Il file HTML non è mai arrivato**: della sessione faceva parte solo il
   PDF del dossier, non `dossier-acquisizione-lugano.html`. I 16 titoli sono
   stati letti dal PDF e sono in `lots.py`, ma le sostituzioni vanno fatte
   girare sul file originale.

## Uso

```bash
export COMICVINE_API_KEY=...        # chiave gratuita: comicvine.gamespot.com/api
./run_all.sh /percorso/dossier-acquisizione-lugano.html
```

Oppure un passo alla volta:

```bash
python3 fetch_covers.py --out covers          # 1. scarica le copertine
python3 patch_html.py dossier.html --dry-run  # 2. mostra le sostituzioni
python3 patch_html.py dossier.html            #    le applica (lascia un .bak)
python3 export_pdf.py dossier.html            # 3. PDF A4 + verifica impaginazione
```

Serve solo Python 3.8+ (libreria standard) e Chrome o Chromium. Nessuna
dipendenza da installare.

## I file

| file | cosa fa |
| --- | --- |
| `lots.py` | i 16 lotti: come riconoscerli dall'`<h3>`, dove stanno su Comic Vine, che anno di copertina aspettarsi |
| `fetch_covers.py` | interroga l'API, scarica le copertine, scrive `manifest.json` e il provino di controllo |
| `patch_html.py` | sostituisce i `<div class="plate">` con gli `<img>` |
| `export_pdf.py` | stampa in A4 con Chrome headless e verifica che nessuna scheda si spezzi |
| `run_all.sh` | i tre passi in fila |
| `selftest.py` | prova l'intera catena su un dossier sintetico, senza rete |
| `test_matching.py` | verifica che la scelta del volume scarti ristampe e rilanci |

## Come si evitano le ristampe

Il punto delicato è il quarto della richiesta: prendere *Uncanny X-Men* #221
del 1987 e non il facsimile del 2019. Una ricerca libera sul titolo le
restituisce entrambe, così la risoluzione avviene in due passi:

1. **il volume**, scelto per nome, anno di inizio della testata originale,
   editore e numero di albi pubblicati. Un volume troppo corto per contenere
   il numero cercato viene escluso: è il filtro che elimina raccolte e
   facsimili. L'anno pesa più del nome, perché i rilanci si chiamano
   esattamente come l'originale;
2. **il numero** dentro quel volume, con la data di copertina restituita
   dall'API confrontata con l'anno atteso. Ogni scostamento superiore a un
   anno diventa un avviso nel report e un riquadro rosso nel provino.

Alla fine `covers/contact-sheet.html` mostra le 16 copertine in griglia, ognuna
accanto al numero e all'anno che dovrebbe avere: è lì che si fa il controllo a
occhio in un colpo solo.

Casi particolari già impostati in `lots.py`:

- **Daredevil: Love and War** è *Marvel Graphic Novel* #24, non una serie
  propria; viene cercato prima lì.
- **Weapon X** esce su *Marvel Comics Presents* #72–84: si prende la copertina
  del #72.
- **Elektra: Assassin**, **Parable**, **Requiem**, **1234**, **Marvels**,
  **Moonshadow**, **Secret Wars** sono lotti su serie intere: si scarica la
  copertina del #1. Per *Marvels* il dossier segnala il #4 (morte di Gwen)
  come il più ricercato — se preferisci quella in catalogo, cambia
  `issue_number` nel lotto 8.
- **New Mutants #18** è dato nel dossier come dicembre 1984, ma la data di
  copertina dell'albo è agosto 1984: lo scarto è entro l'anno e lo script lo
  segnala come plausibile senza bloccarsi.
- **Incursions #1** è annunciato per novembre 2026 e potrebbe non essere
  ancora schedato su Comic Vine: in quel caso il lotto resta senza copertina e
  il suo segnaposto non viene toccato.

## L'impaginazione

`export_pdf.py` applica in stampa `break-inside: avoid` a ogni `.lot`: Chrome
sposta la scheda intera alla pagina dopo invece di tagliarla. Quella regola non
può però nulla se una scheda è **più alta della pagina stampabile**, ed è
l'unico caso in cui una scheda si spezza davvero. Lo script misura quindi
l'altezza reale di ogni scheda alla larghezza di colonna dell'A4 e segnala
quelle che non ci stanno, poi rilegge il PDF prodotto per controllare numero di
pagine e MediaBox (595×842 pt). Se una scheda sfora: `--margin 10`, testo più
corto, o copertina più piccola.

Il CSS esistente non viene riscritto. L'`<img>` eredita le classi del `div`
sostituito — ombra, margini e posizione in colonna continuano ad applicarsi — e
un piccolo blocco `<style id="lugano-covers-css">` aggiunto in `<head>` fissa
`max-width: 190px` e `border-radius: 3px`. `patch_html.py` è idempotente:
rieseguito aggiorna le immagini invece di duplicarle, e lascia sempre un `.bak`.

## Test

```bash
python3 test_matching.py   # scelta del volume, senza rete
python3 selftest.py        # catena completa su un dossier sintetico
```

Il selftest costruisce 16 schede finte con copertine generate al volo, applica
le sostituzioni due volte (per verificare l'idempotenza), produce il PDF e
controlla che sia A4 e senza schede spezzate.
