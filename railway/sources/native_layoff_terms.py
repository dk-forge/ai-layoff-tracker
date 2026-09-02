"""The layoff vocabulary of each language the news net reads, in ONE place.

WHY THIS EXISTS (measured 2026-09-02, worldwide-coverage audit).

The tracker's worldwide news reach ran through three collectors and every one
of them asked its non-English half in English:

  * `sources/google_news.py` rotated 45 national editions and put the same
    five ENGLISH `DISCOVERY_QUERIES` to all of them. `sources/local_news.py`
    had already measured (2026-08-13) what that returns: an English query on
    `hl=de&gl=CH` yields the worldwide English feed, not that country's news.
    Thirty-four of the 45 editions are non-English, so the Sources page's
    "we search each market in its own language" described 11 editions.
  * `sources/gdelt.py` carried precision-selected `NATIVE_TERMS` for the public
    DOC API, which has abandoned the broad window on 100% of measured runs
    since 2026-08-19 (TECHLOG 2026-08-30). The path that actually runs is the
    BigQuery mirror, whose title regex was built from `discovery_terms()` -- the
    English vocabulary -- against ORIGINAL-language page titles. A Handelsblatt
    headline reading "Stellenabbau" matched only if GDELT's theme tagger had
    also filed it under UNEMPLOYMENT.
  * `sources/local_news.py` had the right idea and its own per-language query
    sets, for 25 markets that share almost nothing with the 45 editions above.

So the same language was written three times or not at all. This module is the
single table the collectors read, keyed by the `hl` language Google News uses
and by the bare phrase the mirror's regex needs.

PROVENANCE, per language. Nothing here is invented for this file:

  de fr es it nl pl sv pt zh   `sources/gdelt.py NATIVE_TERMS`: the precision-
                               selected subset of a 12-language sweep
                               (2026-07-24, three independent model
                               consultations agreed, each term verified to mean
                               only mass job cuts). Kept as a LITERAL there
                               because `tests/test_rotation_covers_ring.py`
                               reads that ring by AST; `test_worldwide_vocabulary`
                               pins that every one of those terms is also here.
  ar fr es pt ru tr            `sources/local_news_markets.py`, measured against
                               live editions 2026-08-13 (and the Russian set's
                               deliberate exclusion of bare "увольнения").
  ja ko                        `sources/layoff_language.py STRONG_TERMS_*`,
                               researched 2026-07-18 with EDINET/DART fixture
                               evidence, strong tier only.
  da no fi cs ro hu th vi      NEW here, and honestly labelled as such: these
                               are the standard collective-dismissal words of
                               each language (the legal term plus the headline
                               word), NOT a precision-sampled set. They are
                               discovery terms only. Every hit still passes the
                               free locality checks, the pre-extraction gate and
                               the extractor, and `google_news.MAX_ITEMS` bounds
                               what a run can spend, so a noisy term costs
                               candidates, never rows. The first month of
                               `railway/spend_jobs.json` per-source rows is the
                               measurement that should prune them.

Two readers:

  `google_news_queries(hl)`  the query strings for one Google News edition,
                             or () when the language has no vocabulary here.
                             An empty answer means SKIP that edition, never
                             "ask it in English" -- that was measured to return
                             the global feed, i.e. paid duplicates.
  `mirror_title_terms()`     every bare phrase, for the BigQuery mirror's
                             REGEXP_CONTAINS over lowercased page titles. Same
                             scan, same bytes: the regex grows, the partition
                             filter does not.

Nothing here performs a network call or writes a row.
"""
from __future__ import annotations

# Bare phrases per language. Each entry is ONE phrase (no OR, no quotes); the
# readers below quote and join them for the surface that needs it.
PHRASES_BY_LANG: dict[str, tuple[str, ...]] = {
    "de": ("Stellenabbau", "Massenentlassung", "Entlassungen", "Arbeitsplätze streichen"),
    "fr": ("suppression de postes", "suppressions de postes", "licenciement collectif",
           "licenciements collectifs", "plan social", "plan de sauvegarde de l'emploi"),
    "es": ("despido colectivo", "despidos colectivos", "recorte de plantilla",
           "recorte de personal", "despidos masivos", "expediente de regulación de empleo"),
    "it": ("licenziamento collettivo", "licenziamenti collettivi", "esuberi", "licenziamenti"),
    "nl": ("massaontslag", "collectief ontslag", "banen geschrapt", "reorganisatie banen"),
    "pl": ("zwolnienia grupowe", "redukcja etatów", "zwolnienia pracowników"),
    "sv": ("varsel om uppsägning", "varslar om uppsägning", "personalneddragningar"),
    "pt": ("demissão em massa", "despedimento coletivo", "despedimento colectivo",
           "corte de postos de trabalho", "redução de pessoal", "demissões"),
    "zh": ("大规模裁员", "裁員", "裁员", "大量解僱"),
    "ar": ("تسريح العمال", "تسريح موظفين", "الاستغناء عن موظفين", "تقليص العمالة", "تسريح جماعي"),
    "ru": ("сокращение штата", "сокращение персонала", "сокращение сотрудников",
           "массовое сокращение", "сокращение рабочих мест"),
    "tr": ("toplu işten çıkarma", "işten çıkarma", "personel azaltma", "kadro daraltma"),
    "ja": ("整理解雇", "希望退職", "早期退職", "人員削減", "人員整理"),
    "ko": ("정리해고", "희망퇴직", "명예퇴직", "인력감축", "인원감축", "구조조정 해고"),
    # --- new here, see PROVENANCE above ---
    "da": ("massefyring", "afskedigelser", "fyringsrunde", "nedlægger stillinger"),
    "no": ("nedbemanning", "masseoppsigelse", "oppsigelser", "kutter stillinger"),
    "fi": ("irtisanomiset", "irtisanoo", "yt-neuvottelut", "muutosneuvottelut"),
    "cs": ("hromadné propouštění", "propouštění zaměstnanců", "rušení pracovních míst"),
    "ro": ("concedieri colective", "disponibilizări", "concedieri"),
    "hu": ("csoportos létszámleépítés", "létszámleépítés", "leépítés"),
    "th": ("เลิกจ้างพนักงาน", "ปลดพนักงาน", "เลิกจ้างจำนวนมาก"),
    "vi": ("cắt giảm nhân sự", "sa thải hàng loạt", "cắt giảm lao động"),
}

# Google News `hl` codes that mean English. An edition in this set keeps the
# English discovery vocabulary; every other edition is asked in its own words.
ENGLISH_HL_PREFIX = "en"


def language_of_hl(hl: str) -> str:
    """`de` for `de`, `pt` for `pt-BR`, `zh` for `zh-TW`, `en` for `en-IN`."""
    return (hl or "").strip().lower().split("-", 1)[0]


def is_english_hl(hl: str) -> bool:
    return language_of_hl(hl) == ENGLISH_HL_PREFIX


def google_news_queries(hl: str) -> tuple[str, ...]:
    """Query strings for one Google News edition, in that edition's language.

    Two queries per language -- the legal/collective phrases and the headline
    phrases -- so a run's `MAX_ITEMS` share is spent on two different angles
    rather than one long OR-chain. Returns () for a language with no
    vocabulary here; the caller must SKIP that edition (see module docstring).
    """
    phrases = PHRASES_BY_LANG.get(language_of_hl(hl), ())
    if not phrases:
        return ()
    half = (len(phrases) + 1) // 2
    groups = [phrases[:half], phrases[half:]] if len(phrases) > 1 else [phrases]
    return tuple(" OR ".join(f'"{p}"' for p in g) for g in groups if g)


def mirror_title_terms() -> tuple[str, ...]:
    """Every bare phrase, deduplicated, for the mirror's title regex."""
    out: list[str] = []
    for phrases in PHRASES_BY_LANG.values():
        for p in phrases:
            if p not in out:
                out.append(p)
    return tuple(out)


def languages() -> tuple[str, ...]:
    return tuple(PHRASES_BY_LANG)
