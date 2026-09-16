"""Does one employer name mean the same employer as another?

WHY THIS IS ITS OWN MODULE. Every dedup defence in this repo buckets on a
company name before anything is compared, so two spellings of one employer make
two buckets and the pair is never proposed, never compared, never judged, at
zero cost, forever (docs/TECHLOG.md 2026-09-16, the LAUSD pair). The answer to
that was `duplicate_article_rows`, whose key holds NO name at all -- it catches
the case where the two rows cite the SAME article. On 2026-09-07/08 the same
class arrived through a door that key cannot reach: Jaguar Land Rover's 4,000
job cuts stored four times, from four DIFFERENT outlets, under "Jaguar Land
Rover", "JLR", "Tata Motors' JLR" and the Chinese-language "捷豹路虎". Four
articles, four URLs, one event, and three of them summed into the Week 37
reader digest.

So a guard for that class has to answer the name question after all. It answers
it CONSERVATIVELY and it answers it in one place, here, so the invariant, the
plugin and the tests cannot hold three opinions about it.

THREE WAYS TWO NAMES CAN BE ONE EMPLOYER, and nothing else counts:

  1. THE SAME CANONICAL KEY. `entity_key` mirrors the plugin's
     alt_company_key/alt_canonical_company (includes/api.php): punctuation out,
     legal forms and trailing geographic qualifiers out, then the hand-kept
     alias map that folds subsidiaries, rebrands and parents onto one key.

  2. AN INITIALISM. "JLR" is the initials of "Jaguar Land Rover". Both sides
     must survive the key normalisation, the long side must carry at least two
     tokens, and the short side must be a single token of at least two
     characters that equals those initials exactly. "IBM" and "International
     Business Machines" is the same shape; "HP" and "Hewlett Packard" is
     already in the alias map and needs no rule.

  3. TOKEN CONTAINMENT WITH A DISTINCTIVE HEAD. "Tata Motors' JLR" contains
     "JLR". The contained side's tokens must ALL appear in the container, the
     contained side must not be a bare generic or geographic word, and the
     contained side must carry at least one token that is not a corporate
     stopword. This is the loosest of the three and it is the one measured
     hardest below.

A NON-LATIN NAME CANNOT BE NORMALISED, IT CAN ONLY BE KNOWN. alt_company_key
strips every character outside [a-z0-9 ], so "捷豹路虎" normalises to the EMPTY
STRING and always has: a CJK-named row has no company key at all, in the plugin
and in every Python mirror of it. Nothing here can infer that those four glyphs
are Jaguar Land Rover. `NON_LATIN_ALIASES` is the only door, it is a hand-kept
list, and it is deliberately small: an entry is a fact somebody established,
never a guess. A name that reaches none of the three rules above is UNKNOWN,
which here means "not the same employer as far as this module can tell", and
the guard that calls it simply does not fire. That is the safe direction: a
missed duplicate is a visible, countable, reversible row on the tracker, and a
false one is a merge proposal against a row nobody can get back.

Pure: no network, no keys, no model.
"""
import re
import unicodedata

#: Mirrors alt_canonical_company() in wordpress-plugin/.../includes/api.php.
#: tests/test_entity_resolution.py parses that PHP map and fails when a pair
#: lives there and not here, so the two cannot drift apart unnoticed.
ALIASES = {
    'google': 'alphabet', 'youtube': 'alphabet', 'waymo': 'alphabet',
    'facebook': 'meta', 'meta platforms': 'meta', 'instagram': 'meta', 'whatsapp': 'meta',
    'twitter': 'x', 'x twitter': 'x',
    'amazon com': 'amazon', 'amazon web services': 'amazon', 'aws': 'amazon', 'twitch': 'amazon',
    'aws amazon': 'amazon', 'amazon fresh': 'amazon',
    'optum': 'unitedhealth', 'unitedhealth': 'unitedhealth',
    'unitedhealthcare': 'unitedhealth', 'united health': 'unitedhealth',
    'block square': 'block', 'square': 'block', 'cash app': 'block',
    'linkedin': 'microsoft', 'github': 'microsoft', 'xbox': 'microsoft',
    'activision blizzard': 'microsoft', 'bungie': 'microsoft',
    'hewlett packard': 'hp', 'hewlett-packard': 'hp', 'hp inc': 'hp',
    'paramount skydance': 'paramount', 'paramount global': 'paramount', 'cbs': 'paramount',
    'warner bros discovery': 'warner bros', 'wbd': 'warner bros',
    'cnn': 'warner bros', 'hbo': 'warner bros',
    'nbcuniversal': 'comcast', 'nbc universal': 'comcast',
    'xfinity': 'comcast', 'versant': 'comcast',
    'saks fifth avenue': 'saks', 'saks global': 'saks', 'neiman marcus': 'saks',
    'blueoval sk': 'ford', 'blueoval': 'ford', 'bosk': 'ford',
    'ultium cells': 'general motors', 'factory zero': 'general motors', 'gm': 'general motors',
    'conduent commercial': 'conduent', 'conduent federal': 'conduent',
    'conduent state local': 'conduent', 'conduent business process': 'conduent',
    'conduent education': 'conduent', 'conduent state healthcare': 'conduent',
    'conduent corporate': 'conduent', 'conduent commercial solutions': 'conduent',
    'tata consultancy services': 'tcs',
    'bristol myers squibb': 'bristol myers', 'bristol-myers squibb': 'bristol myers',
    'bms': 'bristol myers',
    'alphabet': 'alphabet', 'meta': 'meta',
    # 2026-09-16, the incident this module was written for. JLR is the
    # employer's own current trading name and the name it confirmed the cuts
    # under; "Jaguar Land Rover" is the legal name and the one the corpus
    # already holds history against, so that is the canonical side.
    'jlr': 'jaguar land rover',
    'tata motors jlr': 'jaguar land rover',
    'jaguar land rover automotive': 'jaguar land rover',
}

#: Names that carry no Latin characters at all, so no normaliser can reach
#: them. Keyed on the NFKC-folded, whitespace-stripped raw name. Every entry is
#: an employer somebody identified by reading the row's own source; this list
#: is never grown by inference.
NON_LATIN_ALIASES = {
    '捷豹路虎': 'jaguar land rover',          # zh: Jaguar Land Rover
    'ジャガー・ランドローバー': 'jaguar land rover',   # ja: Jaguar Land Rover
}

#: The plugin's own two strip lists, in the plugin's own order.
_LEGAL_RX = re.compile(
    r'\b(inc|incorporated|corp|corporation|co|company|ltd|limited|plc|llc|lp'
    r'|group|holdings|holding|technologies|technology|systems|solutions|the|com)\b')
_GEO_RX = re.compile(r'\b(america|americas|usa|us|international|global|worldwide|na)\b')

#: A token that carries no employer identity on its own. A containment match
#: whose contained side is only these is not evidence of anything: "Tata" is
#: the contained side of both "Tata Steel" and "Tata Motors", which are two
#: employers, and "Health" is the contained side of a hundred.
_WEAK_TOKENS = {
    'health', 'healthcare', 'motors', 'motor', 'steel', 'bank', 'media',
    'energy', 'foods', 'food', 'retail', 'stores', 'store', 'services',
    'service', 'industries', 'industrial', 'national', 'american', 'united',
    'general', 'first', 'new', 'north', 'south', 'east', 'west', 'central',
    'auto', 'automotive', 'air', 'airlines', 'airways', 'insurance', 'capital',
    'financial', 'partners', 'associates', 'consulting', 'digital', 'labs',
    'works', 'brands', 'products', 'mobility', 'logistics', 'university',
    'hospital', 'medical', 'school', 'district', 'county', 'city', 'state',
}


def _fold(name):
    """NFKC, lowercased, and with the width/quote variants folded out.

    A curly apostrophe is not a different employer from a straight one, and
    "Tata Motors’ JLR" arrives with a curly one from every Indian outlet.
    """
    text = unicodedata.normalize('NFKC', str(name or '')).lower()
    return text.replace('’', "'").replace('‘', "'").strip()


def entity_key(name):
    """The employer identity key, or '' when the name yields none.

    Mirrors alt_company_key(): strip to [a-z0-9 ], drop legal forms and
    trailing geographic qualifiers, collapse whitespace, then the alias map.
    A name with no Latin characters returns its NON_LATIN_ALIASES canonical
    key if it has one, and otherwise '' -- exactly as the plugin's key does,
    stated rather than papered over.
    """
    folded = _fold(name)
    if not folded:
        return ''
    compact = re.sub(r'\s+', '', folded)
    if compact in NON_LATIN_ALIASES:
        return NON_LATIN_ALIASES[compact]
    key = re.sub(r'[^a-z0-9 ]', ' ', folded)
    key = _LEGAL_RX.sub(' ', key)
    key = _GEO_RX.sub(' ', key)
    key = re.sub(r'\s+', ' ', key).strip()
    if not key:
        return ''
    return ALIASES.get(key, key)


def _tokens(key):
    return [t for t in key.split(' ') if t]


def _initialisms(name, key):
    """Every initialism the long side could reasonably be written as.

    TWO FORMS, BECAUSE THE KEY THROWS AWAY LETTERS THE INITIALISM KEEPS.
    `entity_key` drops legal forms and trailing geographic qualifiers, so
    "International Business Machines" normalises to "business machines" and its
    key initials are "bm" -- while the initialism everyone writes is IBM. So the
    initials are taken from the key AND from the raw name with punctuation
    stripped, and either may match.
    """
    forms = set()
    for tokens in (_tokens(key),
                   _tokens(re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', _fold(name))).strip())):
        if len(tokens) >= 2:
            forms.add(''.join(t[0] for t in tokens if t))
    return forms


def _is_initialism_of(short_key, long_name, long_key):
    short = _tokens(short_key)
    if len(short) != 1:
        return False
    word = short[0]
    if len(word) < 2 or not word.isalpha():
        return False
    return word in _initialisms(long_name, long_key)


def _is_contained_in(short_key, long_key):
    short = set(_tokens(short_key))
    long_tokens = set(_tokens(long_key))
    if not short or short == long_tokens or not short <= long_tokens:
        return False
    # The contained side has to carry identity of its own. All-weak means the
    # match is "Tata" inside "Tata Steel", which is not evidence.
    return any(t not in _WEAK_TOKENS and len(t) > 2 for t in short)


def same_entity(name_a, name_b):
    """True when two employer names resolve to ONE employer.

    Returns False for anything it cannot establish, including a name it cannot
    normalise at all. See the module docstring for why that direction.
    """
    key_a, key_b = entity_key(name_a), entity_key(name_b)
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    (short, _), (long_key, long_name) = sorted(
        ((key_a, name_a), (key_b, name_b)), key=lambda pair: len(pair[0]))
    return (_is_initialism_of(short, long_name, long_key)
            or _is_contained_in(short, long_key))


def why_same_entity(name_a, name_b):
    """The rule that joined two names, for a guard's own sentence. '' if none."""
    key_a, key_b = entity_key(name_a), entity_key(name_b)
    if not key_a or not key_b:
        return ''
    if key_a == key_b:
        folded_a = re.sub(r'\s+', '', _fold(name_a))
        folded_b = re.sub(r'\s+', '', _fold(name_b))
        if folded_a in NON_LATIN_ALIASES or folded_b in NON_LATIN_ALIASES:
            return 'a recorded non-Latin spelling'
        return 'the same canonical company key'
    (short, _), (long_key, long_name) = sorted(
        ((key_a, name_a), (key_b, name_b)), key=lambda pair: len(pair[0]))
    if _is_initialism_of(short, long_name, long_key):
        return 'an initialism of the other'
    if _is_contained_in(short, long_key):
        return 'one name contained in the other'
    return ''
