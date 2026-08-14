"""What each collector is WORTH, and where else its data can be got.

WHY THIS FILE EXISTS. The health system could already tell that a collector had
broken, and it mailed the owner about it. What it could not do was say what the
breakage cost or what to try instead, so every repair started from "parser
returned 0, check PDF layout" and a human reading a scraper cold. On 2026-08-13
`warn_quebec` had been sitting at that message for days. Quebec is the only
named per-employer layoff register in Canada and its statutory floor is 10
employees against US WARN's 50; the actual fault was that ONE scraped HTML page
had stopped answering from CI while the PDFs behind it were fine and reachable.
Nothing in the alert said either thing. The owner's question was the right one:
why did it not go looking for another route?

So two facts per source, kept next to each other because they are useless apart:

  worth   one line on what this collector sees that nothing else does. It turns
          "warn_quebec degraded" into "Quebec, the only named layoff register in
          Canada and the only one with a 10-employee floor, has returned 0 for
          6 days". The first is a status; the second is a decision.

  routes  the alternate ways to the SAME data, named in advance, so a repair
          starts with candidates instead of a shrug. These are researched once,
          while the source is healthy and there is time, not at 2am.

  zero_is_outage
          whether a run returning zero rows is a FAILURE or just a quiet period.
          This is DECLARED, not learned. A monthly register that we re-read four
          months deep can never legitimately return nothing, so its zero is an
          outage. A bankruptcy watchlist that found no distressed employers this
          week genuinely found none, and calling that an outage would teach the
          owner to ignore the channel -- which is the failure mode that matters
          most here. When in doubt leave it False: a false alarm costs more
          trust than a missed one costs data, because the missed one is still
          caught by the staleness clock.

This registry is DESCRIPTIVE and additive. A source that is not listed behaves
exactly as it did before, so adding a source can never silently arm an alarm.
"""

# Sources whose zero is a real outage, with what the outage costs and what to
# try. Keep `worth` to one sentence a tired person can act on.
SOURCE_VALUE = {
    "warn_quebec": {
        "worth": (
            "Quebec's monthly collective-dismissal register (MESS) is the ONLY "
            "public per-employer layoff register in Canada, and its statutory "
            "floor is 10 employees against US WARN's 50, so it names employers "
            "no other collector here can see"),
        "zero_is_outage": True,
        "routes": [
            "the monthly PDFs are reachable WITHOUT the HTML landing page: build "
            "the URL from CDN_TEMPLATE in railway/sources/quebec.py "
            "(LI_licenciement-collectif_YYYY-MM_MESS.pdf) and fetch it directly",
            "compare the parsed count against the 'Total - Nombre d'avis' line "
            "each PDF prints for itself; that number is the ground truth for "
            "whether a run was thin",
            "web.archive.org holds snapshots of both the landing page and the "
            "PDFs if the CDN itself is the thing that moved",
        ],
    },
    "warn_mazowieckie": {
        "worth": (
            "WUP Warszawa is the only one of Poland's 16 voivodeship labour "
            "offices that names employers, so it is the single named layoff "
            "register for Poland"),
        # A monthly register legitimately has months with no new post.
        "zero_is_outage": False,
        "routes": [
            "the register is monthly press posts; check whether the post URL "
            "pattern or the listing page moved before touching the parser",
        ],
    },
    "warn_us": {
        "worth": (
            "state WARN notices are the statutory backbone of US coverage and "
            "the largest single source of stored rows"),
        # Never zero across all states; a zero here is a total collapse.
        "zero_is_outage": True,
        "routes": [
            "the per-state floors in railway/warn_state_baselines.json say what "
            "each state normally yields, so compare per state rather than in "
            "total: one dead state hides inside a healthy national number",
            "warn-scraper upstream may have moved a state's scraper; the custom "
            "parsers in railway/warn_custom.py are the fallback route",
        ],
    },
    "eurofound_erm": {
        "worth": (
            "Eurofound ERM is the compiled restructuring record for the EU/EEA, "
            "where national labour filings are confidential and news is "
            "otherwise the only route"),
        "zero_is_outage": False,
        "routes": [
            "ERM publishes in waves, so a quiet run is normal; confirm against "
            "the ERM site's own most recent event date before assuming breakage",
        ],
    },
}

# What to say when a source we have not characterised returns zero. Honest about
# being generic rather than pretending to knowledge this registry does not hold.
GENERIC_ROUTES = [
    "check whether the third-party site changed shape (layout, URL pattern, or "
    "a WAF/bot wall) BEFORE editing the parser -- a scraper that returns 0 has "
    "usually lost its discovery step, not its parsing step",
    "if discovery goes through one scraped HTML page, look for a route that "
    "does not: a constructible URL pattern, an open-data/CKAN endpoint, an RSS "
    "feed, or a Wayback snapshot",
]


def value_of(source):
    """The registry entry for `source`, or None if it is not characterised."""
    return SOURCE_VALUE.get(source)


def zero_is_outage(source):
    """Is a zero-row run from this source a data outage? Declared, not learned."""
    return bool((SOURCE_VALUE.get(source) or {}).get("zero_is_outage"))


def worth_line(source):
    """One line on what this collector sees that nothing else does, or ''."""
    return (SOURCE_VALUE.get(source) or {}).get("worth", "")


def routes_for(source):
    """Candidate alternate routes to the same data. Never empty."""
    return list((SOURCE_VALUE.get(source) or {}).get("routes") or GENERIC_ROUTES)


def escalation_line(source, detail=""):
    """The one line an alert should lead with for a zero-returning collector.

    Names the source, what it is worth, and that it is currently returning
    nothing -- so the reader can decide without opening a dashboard.
    """
    worth = worth_line(source)
    if not worth:
        return f"{source} is returning no rows. {str(detail)[:120]}".strip()
    return (f"{source} is returning NO ROWS, and it is not a minor collector: "
            f"{worth}.")


def repair_brief(source):
    """A paste-ready block naming this source's candidate routes."""
    lines = [f"{source}: candidate routes to the same data, try these first:"]
    for r in routes_for(source):
        lines.append(f"  - {r}")
    return "\n".join(lines)
