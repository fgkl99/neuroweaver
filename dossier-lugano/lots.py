"""Single source of truth for the 16 lots of the Lugano acquisition dossier.

Each lot records:
  * how to recognise it from the <h3> of its <article class="lot">;
  * which Comic Vine volume/issue holds the ORIGINAL US edition
    (several probes, tried in order, so graphic novels and anthology
    runs still resolve);
  * the cover year we expect, used to flag reprints and wrong editions.
"""

from dataclasses import dataclass, field
import re
import unicodedata


@dataclass(frozen=True)
class Probe:
    """One candidate (volume, issue) location on Comic Vine."""

    volume_query: str          # what to send to /volumes/?filter=name:...
    volume_start_year: int     # start year of the ORIGINAL run
    issue_number: str
    publishers: tuple = ("marvel", "epic comics", "marvel knights")
    min_issue_count: int = 1   # reject short reprint/collection volumes


@dataclass(frozen=True)
class Lot:
    number: int
    slug: str
    label: str                 # human label used in alt text and reports
    expect_cover_year: int
    probes: tuple
    h3_pattern: str            # matched against the normalised <h3> text
    note: str = ""

    def matches_h3(self, text: str) -> bool:
        return re.search(self.h3_pattern, normalise(text)) is not None


def normalise(text: str) -> str:
    """Lowercase, strip accents, and flatten the dashes/quotes used in the dossier."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("—", " ").replace("–", "-").replace("‒", "-")
    text = text.replace("«", " ").replace("»", " ").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


LOTS = (
    Lot(
        number=1,
        slug="new-mutants-18",
        label="New Mutants #18 (Marvel, 1984)",
        expect_cover_year=1984,
        probes=(Probe("New Mutants", 1983, "18", min_issue_count=18),),
        h3_pattern=r"new mutants\s*#?\s*18\b",
    ),
    Lot(
        number=2,
        slug="new-mutants-26",
        label="New Mutants #26 (Marvel, 1985)",
        expect_cover_year=1985,
        probes=(Probe("New Mutants", 1983, "26", min_issue_count=26),),
        h3_pattern=r"new mutants\s*#?\s*26\b",
    ),
    Lot(
        number=3,
        slug="elektra-assassin-1",
        label="Elektra: Assassin #1 (Epic, 1986)",
        expect_cover_year=1986,
        probes=(Probe("Elektra: Assassin", 1986, "1", publishers=("epic comics", "marvel")),),
        h3_pattern=r"elektra:? assassin",
        note="Miniserie in 8 numeri: si scarica la copertina del #1.",
    ),
    Lot(
        number=4,
        slug="daredevil-love-and-war",
        label="Daredevil: Love and War (Marvel Graphic Novel #24, 1986)",
        expect_cover_year=1986,
        probes=(
            Probe("Marvel Graphic Novel", 1982, "24", min_issue_count=24),
            Probe("Daredevil: Love and War", 1986, "1"),
        ),
        h3_pattern=r"daredevil:? love and war",
    ),
    Lot(
        number=5,
        slug="silver-surfer-parable-1",
        label="Silver Surfer: Parable #1 (Epic, 1988)",
        expect_cover_year=1988,
        probes=(
            Probe("Silver Surfer: Parable", 1988, "1", publishers=("epic comics", "marvel")),
            Probe("Silver Surfer Parable", 1988, "1", publishers=("epic comics", "marvel")),
        ),
        h3_pattern=r"silver surfer:? parable",
        note="Miniserie in 2 numeri: si scarica la copertina del #1.",
    ),
    Lot(
        number=6,
        slug="silver-surfer-requiem-1",
        label="Silver Surfer: Requiem #1 (Marvel Knights, 2007)",
        expect_cover_year=2007,
        probes=(Probe("Silver Surfer: Requiem", 2007, "1"),),
        h3_pattern=r"silver surfer:? requiem",
        note="Miniserie in 4 numeri: si scarica la copertina del #1.",
    ),
    Lot(
        number=7,
        slug="fantastic-four-1234-1",
        label="Fantastic Four: 1234 #1 (Marvel Knights, 2001)",
        expect_cover_year=2001,
        probes=(Probe("Fantastic Four: 1234", 2001, "1"),),
        h3_pattern=r"fantastic four:? ?1234",
        note="Miniserie in 4 numeri: si scarica la copertina del #1.",
    ),
    Lot(
        number=8,
        slug="marvels-1",
        label="Marvels #1 (Marvel, 1994)",
        expect_cover_year=1994,
        probes=(Probe("Marvels", 1994, "1", min_issue_count=4),),
        h3_pattern=r"^marvels$|^marvels\b(?!\s*(super|comics))",
        note="Miniserie in 4 numeri: copertina del #1 (il #4 e' quello con Gwen).",
    ),
    Lot(
        number=9,
        slug="weapon-x-mcp-72",
        label="Weapon X — Marvel Comics Presents #72 (Marvel, 1991)",
        expect_cover_year=1991,
        probes=(
            Probe("Marvel Comics Presents", 1988, "72", min_issue_count=72),
            Probe("Weapon X", 1991, "1"),
        ),
        h3_pattern=r"weapon x",
        note="La storia esce su Marvel Comics Presents #72-84: copertina del #72.",
    ),
    Lot(
        number=10,
        slug="moonshadow-1",
        label="Moonshadow #1 (Epic, 1985)",
        expect_cover_year=1985,
        probes=(Probe("Moonshadow", 1985, "1", publishers=("epic comics", "marvel")),),
        h3_pattern=r"moonshadow",
        note="Serie in 12 numeri: si scarica la copertina del #1.",
    ),
    Lot(
        number=11,
        slug="uncanny-x-men-221",
        label="Uncanny X-Men #221 (Marvel, 1987)",
        expect_cover_year=1987,
        probes=(
            Probe("Uncanny X-Men", 1963, "221", min_issue_count=221),
            Probe("X-Men", 1963, "221", min_issue_count=221),
        ),
        h3_pattern=r"uncanny x-men\s*#?\s*221\b",
    ),
    Lot(
        number=12,
        slug="uncanny-x-men-168",
        label="Uncanny X-Men #168 (Marvel, 1983)",
        expect_cover_year=1983,
        probes=(
            Probe("Uncanny X-Men", 1963, "168", min_issue_count=168),
            Probe("X-Men", 1963, "168", min_issue_count=168),
        ),
        h3_pattern=r"uncanny x-men\s*#?\s*168\b",
    ),
    Lot(
        number=13,
        slug="uncanny-x-men-266",
        label="Uncanny X-Men #266 (Marvel, 1990)",
        expect_cover_year=1990,
        probes=(
            Probe("Uncanny X-Men", 1963, "266", min_issue_count=266),
            Probe("X-Men", 1963, "266", min_issue_count=266),
        ),
        h3_pattern=r"uncanny x-men\s*#?\s*266\b",
    ),
    Lot(
        number=14,
        slug="secret-wars-1",
        label="Marvel Super Heroes Secret Wars #1 (Marvel, 1984)",
        expect_cover_year=1984,
        probes=(
            Probe("Marvel Super Heroes Secret Wars", 1984, "1", min_issue_count=12),
            Probe("Marvel Super-Heroes Secret Wars", 1984, "1", min_issue_count=12),
        ),
        h3_pattern=r"secret wars",
        note="Maxiserie in 12 numeri: copertina del #1 (non la Secret Wars 2015).",
    ),
    Lot(
        number=15,
        slug="one-world-under-doom-1",
        label="One World Under Doom #1 (Marvel, 2025)",
        expect_cover_year=2025,
        probes=(Probe("One World Under Doom", 2025, "1"),),
        h3_pattern=r"one world under doom",
    ),
    Lot(
        number=16,
        slug="incursions-1",
        label="Incursions #1 (Marvel, 2026)",
        expect_cover_year=2026,
        probes=(Probe("Incursions", 2026, "1"),),
        h3_pattern=r"incursions",
        note="Uscita annunciata per novembre 2026: puo' non essere ancora su Comic Vine.",
    ),
)

BY_SLUG = {lot.slug: lot for lot in LOTS}


def match_lot(h3_text: str):
    """Return the single lot whose pattern matches this <h3>, or None.

    Raises if the heading is ambiguous, so a mis-mapped cover can never be
    written into the dossier silently.
    """
    hits = [lot for lot in LOTS if lot.matches_h3(h3_text)]
    if not hits:
        return None
    if len(hits) > 1:
        raise ValueError(
            f"<h3> ambiguo {h3_text!r}: corrisponde a {[l.slug for l in hits]}"
        )
    return hits[0]
