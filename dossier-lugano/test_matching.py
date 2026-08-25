#!/usr/bin/env python3
"""Test offline della logica che sceglie volume e numero su Comic Vine.

Non serve rete né chiave: la risposta dell'API viene simulata con dei richiami
plausibili (rilanci omonimi, ristampe, raccolte) per verificare che venga
scelta sempre l'edizione USA originale.

    python3 test_matching.py
"""

import sys

import fetch_covers
from lots import BY_SLUG

MARVEL = {"name": "Marvel"}
EPIC = {"name": "Epic Comics"}

# Come Comic Vine risponde davvero a filter=name:<query>: il volume giusto
# in mezzo a rilanci, ristampe ed edizioni facsimile.
FAKE_VOLUMES = {
    "Uncanny X-Men": [
        {"id": 2133, "name": "Uncanny X-Men", "start_year": 1963,
         "count_of_issues": 544, "publisher": MARVEL},
        {"id": 40123, "name": "Uncanny X-Men", "start_year": 2011,
         "count_of_issues": 20, "publisher": MARVEL},
        {"id": 50777, "name": "Uncanny X-Men", "start_year": 2018,
         "count_of_issues": 22, "publisher": MARVEL},
        {"id": 61234, "name": "Uncanny X-Men Facsimile Edition", "start_year": 2019,
         "count_of_issues": 6, "publisher": MARVEL},
        {"id": 9001, "name": "Essential Uncanny X-Men", "start_year": 2006,
         "count_of_issues": 1, "publisher": MARVEL},
    ],
    "New Mutants": [
        {"id": 2222, "name": "The New Mutants", "start_year": 1983,
         "count_of_issues": 100, "publisher": MARVEL},
        {"id": 3333, "name": "New Mutants", "start_year": 2003,
         "count_of_issues": 13, "publisher": MARVEL},
        {"id": 4444, "name": "New Mutants", "start_year": 2009,
         "count_of_issues": 50, "publisher": MARVEL},
        {"id": 5555, "name": "New Mutants Classic", "start_year": 2006,
         "count_of_issues": 7, "publisher": MARVEL},
    ],
    "Marvels": [
        {"id": 6001, "name": "Marvels", "start_year": 1994,
         "count_of_issues": 4, "publisher": MARVEL},
        {"id": 6002, "name": "Marvels", "start_year": 2019,
         "count_of_issues": 1, "publisher": MARVEL},
        {"id": 6003, "name": "Marvels Epilogue", "start_year": 2019,
         "count_of_issues": 1, "publisher": MARVEL},
    ],
    "Moonshadow": [
        {"id": 7001, "name": "Moonshadow", "start_year": 1985,
         "count_of_issues": 12, "publisher": EPIC},
        {"id": 7002, "name": "Moonshadow", "start_year": 1994,
         "count_of_issues": 12, "publisher": {"name": "Vertigo"}},
    ],
    "Marvel Comics Presents": [
        {"id": 8001, "name": "Marvel Comics Presents", "start_year": 1988,
         "count_of_issues": 175, "publisher": MARVEL},
        {"id": 8002, "name": "Marvel Comics Presents", "start_year": 2007,
         "count_of_issues": 12, "publisher": MARVEL},
        {"id": 8003, "name": "Marvel Comics Presents", "start_year": 2019,
         "count_of_issues": 9, "publisher": MARVEL},
    ],
}

CASES = [
    ("uncanny-x-men-221", "Uncanny X-Men", 2133),
    ("uncanny-x-men-168", "Uncanny X-Men", 2133),
    ("uncanny-x-men-266", "Uncanny X-Men", 2133),
    ("new-mutants-18", "New Mutants", 2222),
    ("new-mutants-26", "New Mutants", 2222),
    ("marvels-1", "Marvels", 6001),
    ("moonshadow-1", "Moonshadow", 7001),
    ("weapon-x-mcp-72", "Marvel Comics Presents", 8001),
]


def main():
    failures = []
    for slug, query, expected_id in CASES:
        lot = BY_SLUG[slug]
        probe = next(p for p in lot.probes if p.volume_query == query)
        ranked = sorted(
            ((fetch_covers.score_volume(v, probe), v) for v in FAKE_VOLUMES[query]),
            key=lambda pair: pair[0], reverse=True,
        )
        best_score, best = ranked[0]
        status = "ok  "
        if best["id"] != expected_id:
            status = "FAIL"
            failures.append(f"{slug}: scelto {best['name']} ({best['start_year']}) "
                            f"invece del volume {expected_id}")
        elif best_score <= 0:
            status = "FAIL"
            failures.append(f"{slug}: il volume giusto ha punteggio {best_score}, verrebbe scartato")
        runner_up = f"{ranked[1][1]['name']} ({ranked[1][1]['start_year']}) = {ranked[1][0]}" \
            if len(ranked) > 1 else "—"
        print(f"  {status} {slug:<22} → {best['name']} ({best['start_year']}) "
              f"punteggio {best_score}; secondo: {runner_up}")

    # La data di copertina deve smascherare una ristampa moderna.
    year, source = fetch_covers.cover_year({"cover_date": "2019-08-01"})
    if (year, source) != (2019, "cover_date"):
        failures.append("cover_year() non legge la data di copertina")
    if fetch_covers.pick_image_url({"original_url": "", "super_url": "x/blank.png"}) is not None:
        failures.append("pick_image_url() accetta il segnaposto blank.png")
    if fetch_covers.pick_image_url({"super_url": "x/scale_large/a.jpg"}) != "x/scale_large/a.jpg":
        failures.append("pick_image_url() non ricade su super_url")

    print()
    if failures:
        print("TEST FALLITO:")
        for failure in failures:
            print(f"  · {failure}")
        return 1
    print(f"TEST OK — {len(CASES)} lotti risolti sul volume originale, "
          f"ristampe e rilanci scartati.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
