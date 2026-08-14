"""The reviewable market table for the dormant local-language news collector.

DATA, NOT LOGIC. sources/local_news.py holds the fetching, filtering and
raw-dict construction; everything a human needs to review or correct for a
market lives here, one record per country:

  editions   Google News edition(s) to ask, and the phrase set to ask each one
             in ITS OWN language. Existence of an edition is MEASURED by
             local_news_dryrun.py, never assumed -- several of these countries
             may have no national edition at all, and that is a finding.
  anchors    Free keyword evidence that a headline concerns this country. Used
             ONLY as a pre-LLM cost filter. It never decides what country is
             stored; the extractor does that, as for every other source.
  publishers Curated national news/business outlets. Two jobs: a recognised
             outlet satisfies the country filter when the headline itself
             carries no locality token (the Chopard/Bilanz case), and it lets
             raw_text carry a neutral factual note about where the outlet
             publishes.

PHRASE-SET RULES, learned from measuring these editions on 2026-08-13:
  * COLLECTIVE reduction vocabulary only. Individual-dismissal words return
    employment-law rulings and single-firing stories. Russian bare "увольнения"
    returned a supreme-court ruling on dismissal procedure and a reprimand case
    in its top three; it is excluded in favour of "сокращение штата".
  * Noisy homographs are always PAIRED with a workforce word. A bare Nigerian
    "sack" query returned two child-kidnapping stories in its top three.
  * Where the edition is English but returns the global feed (Kenya, Nigeria,
    Ghana, Sri Lanka, Afghanistan), the queries are LOCALITY-anchored rather
    than translated. Translation is not the fix there; anchoring is.

NOTHING HERE IS AN AGGREGATOR. No layoff-tracker product, no compiled exit
list, no startup-shutdown enumeration. Individual reporting from these
publishers is a source; a product whose purpose is to enumerate layoffs is not,
and sources/local_news.py enforces that structurally on every candidate URL.

NOTHING HERE IS A STATISTICS AGENCY. National statistics institutes, labour
ministries' aggregate series, and multilateral socioeconomic assessments
publish labour-force aggregates: no employer, no headcount attributable to a
decision, no receipt. A statutory notification naming an employer and a
headcount is a source; a monthly unemployment statistic is not. Statistics
bodies are excluded here by construction, and any statutory NOTIFICATION
register found belongs in its own structured collector (like warn_import.py or
the Mazowieckie WUP register), never in this news path.

TIERING. `tier` is a judgement about economy size and press availability, NOT a
measurement. The dry run measures; the tier only orders the report.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Edition:
    """One Google News edition plus the queries to ask it, in its language."""
    lang: str          # human label, e.g. "de-CH"
    hl: str
    gl: str
    ceid: str
    queries: tuple


@dataclass(frozen=True)
class Market:
    country: str       # MUST be the name alt_normalize_country() passes through
    iso2: str
    tier: int
    note: str          # the publication-country phrase appended to raw_text
    editions: tuple
    anchors: tuple
    publishers: tuple = field(default=())


# --- shared phrase sets ----------------------------------------------------
# Arabic, French, Spanish and Portuguese recur across several markets. Defined
# once so a correction lands everywhere at the same time.

AR_QUERIES = (
    '"تسريح العمال" OR "تسريح موظفين" OR "الاستغناء عن موظفين" '
    'OR "تقليص العمالة" OR "تسريح جماعي"',
    '"إغلاق مصنع" OR "خفض عدد الموظفين" OR "إعادة هيكلة" (موظفين OR عمال OR وظائف)',
)

FR_QUERIES = (
    '"licenciements collectifs" OR "suppressions de postes" OR "plan social" '
    'OR "supprime des emplois"',
    '"dépôt de bilan" OR "fermeture de site" OR "plan de sauvegarde de l\'emploi" '
    '(emplois OR salariés OR postes)',
)

ES_QUERIES = (
    '"despidos masivos" OR "desvinculaciones" OR "recorte de personal" '
    'OR "reducción de personal" OR "despido colectivo"',
    '"cierre de planta" OR "expediente de regulación" OR "reestructuración" '
    '(despidos OR trabajadores OR empleos)',
)

PT_QUERIES = (
    '"despedimentos" OR "despedimento colectivo" OR "despedimento coletivo" '
    'OR "corte de postos de trabalho" OR "redução de pessoal"',
    '"reestruturação" OR "encerramento de fábrica" (trabalhadores OR empregos OR postos)',
)

RU_QUERIES = (
    # Collective-reduction phrasing only; bare "увольнения" is excluded.
    '"сокращение штата" OR "сокращение персонала" OR "сокращение сотрудников" '
    'OR "сокращает штат" OR "сокращает персонал"',
    '"массовое сокращение" OR "оптимизация численности" OR "сокращение рабочих мест" '
    'OR "закрытие завода"',
)


def _en_anchored(*places):
    """English collective-layoff queries pinned to a locality.

    For editions that are already English and already reachable by the live
    global sweep, translation is not the gap and anchoring is: the generic
    English query returns the worldwide feed inside the local edition.
    """
    where = " OR ".join(f'"{p}"' if " " in p else p for p in places)
    return (
        f'("layoffs" OR "job cuts" OR "retrenchment" OR "redundancies" '
        f'OR "staff cuts") ({where})',
        f'("lays off" OR "to cut jobs" OR "downsizing" OR "mass retrenchment" '
        f'OR "job losses") ({where})',
    )


MARKETS = (
    # ---------------------------------------------------------------- tier 1a
    # The original five.
    Market(
        "Switzerland", "CH", 1, "a Swiss publication",
        (
            Edition("de-CH", "de", "CH", "CH:de", (
                '"Stellenabbau" OR "Stellen gestrichen" OR "Stellen streichen" '
                'OR "Arbeitsplätze abgebaut"',
                '"Massenentlassung" OR "Massenentlassungen" OR "Sozialplan" '
                'OR "Konsultationsverfahren" (Stellen OR Mitarbeitende OR Arbeitsplätze)',
                '"Stellenabbau" OR "Massenentlassung" (Schweiz OR Schweizer OR Zürich OR Genf OR Basel)',
            )),
            Edition("fr-CH", "fr", "CH", "CH:fr", FR_QUERIES + (
                '"suppressions de postes" OR "plan social" (Suisse OR Genève OR Lausanne OR Vaud)',
            )),
            Edition("it-CH", "it", "CH", "CH:it", (
                '"tagli al personale" OR "licenziamenti collettivi" OR "esuberi" '
                'OR "posti di lavoro soppressi"',
            )),
        ),
        ("schweiz", "schweizer", "suisse", "svizzer", "swiss", "switzerland",
         "zürich", "zurich", "genf", "genève", "geneve", "geneva", "basel",
         "bern", "lausanne", "lugano", "winterthur", "st. gallen", "romandie",
         "waadt", "vaud", "neuchâtel", "neuchatel", "fribourg", "zug",
         "schaffhausen", "seco", "franken", "francs suisses", "chf"),
        ("swissinfo", "finews", "nzz", "neue zürcher zeitung", "handelszeitung",
         "fuw", "finanz und wirtschaft", "le temps", "letemps", "bilanz",
         "tages-anzeiger", "tagesanzeiger", "blick", "watson.ch", "20 minuten",
         "srf", "rts", "24 heures", "tribune de genève", "cash.ch",
         "corriere del ticino", "agefi", "aargauer zeitung", "luzerner zeitung"),
    ),
    Market(
        "Russia", "RU", 1, "a Russian publication",
        (
            Edition("ru-RU", "ru", "RU", "RU:ru", RU_QUERIES + (
                '"сокращение штата" OR "сокращение персонала" (Россия OR Москва OR Петербург)',
            )),
        ),
        ("росси", "москв", "moscow", "russia", "russian", "санкт-петербург",
         "петербург", "petersburg", "рф", "рубл", "ruble", "rouble",
         "екатеринбург", "новосибирск", "казан", "краснодар", "владивосток",
         "челябинск", "самар"),
        ("moscow times", "rbc", "рбк", "kommersant", "коммерсант", "vedomosti",
         "ведомости", "meduza", "медуза", "interfax", "интерфакс",
         "the bell", "forbes.ru", "forbes russia", "cnews", "vc.ru", "banki.ru"),
    ),
    Market(
        "Kenya", "KE", 1, "a Kenyan publication",
        (
            Edition("en-KE", "en-KE", "KE", "KE:en",
                    _en_anchored("Kenya", "Kenyan", "Nairobi", "Mombasa") + (
                        '"retrenchment" OR "redundancy notice" OR "restructuring" '
                        '(Kenya OR Nairobi OR "Kenyan workers")',
                    )),
        ),
        ("kenya", "kenyan", "nairobi", "mombasa", "kisumu", "nakuru", "eldoret",
         "thika", "ksh", "kshs", "kenyan shilling", "safaricom", "kenya power"),
        ("business daily", "businessdailyafrica", "techcabal", "the eastafrican",
         "east african", "kenyan wallstreet", "kenyan wall street",
         "capital fm", "capitalfm", "capital business", "the standard",
         "standardmedia", "nation.africa", "daily nation", "the star",
         "citizen digital", "k24", "people daily"),
    ),
    Market(
        "Nigeria", "NG", 1, "a Nigerian publication",
        (
            Edition("en-NG", "en-NG", "NG", "NG:en",
                    _en_anchored("Nigeria", "Nigerian", "Lagos", "Abuja") + (
                        # Local usage, but precision traps bare: always paired
                        # with a workforce word AND the locality.
                        '("sacks workers" OR "sacked workers" OR "disengage staff" '
                        'OR "disengaged staff" OR "lays off staff") (Nigeria OR Lagos OR Abuja)',
                    )),
        ),
        ("nigeria", "nigerian", "lagos", "abuja", "naira", "₦", "port harcourt",
         "ibadan", "kano", "abeokuta", "benin city", "enugu", "ogun state",
         "rivers state", "nnpc"),
        ("techpoint", "businessday", "business day", "nairametrics", "technext",
         "guardian nigeria", "guardian.ng", "punch", "punchng", "premium times",
         "premiumtimesng", "thecable", "the cable", "thisday", "vanguard",
         "channels television", "channelstv", "leadership", "daily trust",
         "techcabal", "arise news"),
    ),
    Market(
        "Chile", "CL", 1, "a Chilean publication",
        (
            Edition("es-CL", "es-419", "CL", "CL:es-419", ES_QUERIES + (
                '"cierre de faena" OR "necesidades de la empresa" '
                '(despidos OR trabajadores OR empleos)',
                '"despidos" OR "desvinculaciones" (Chile OR Santiago OR Antofagasta '
                'OR "Punta Arenas" OR Valparaíso)',
            )),
        ),
        ("chile", "chilen", "santiago de chile", "valparaíso", "valparaiso",
         "antofagasta", "concepción", "concepcion", "punta arenas", "iquique",
         "temuco", "rancagua", "viña del mar", "codelco", "peso chileno",
         "sernageomin"),
        ("diario financiero", "df.cl", "dfsud", "la tercera", "latercera",
         "pulso", "el mercurio", "economiaynegocios", "emol",
         "diario estrategia", "biobiochile", "la segunda", "cnn chile", "t13",
         "ex-ante", "el mostrador", "cooperativa.cl"),
    ),

    # ---------------------------------------------------------------- tier 1b
    # The fifteen added in the scope extension.
    Market(
        "Turkey", "TR", 1, "a Turkish publication",
        (
            Edition("tr-TR", "tr", "TR", "TR:tr", (
                '"toplu işten çıkarma" OR "işten çıkarma" OR "işten çıkardı" '
                'OR "personel azaltma" OR "kadro daraltma"',
                '"fabrika kapanıyor" OR "üretimi durdurdu" OR "küçülme kararı" '
                '(işçi OR çalışan OR personel)',
            )),
        ),
        ("türkiye", "turkiye", "turkey", "turkish", "istanbul", "i̇stanbul",
         "ankara", "izmir", "i̇zmir", "bursa", "kocaeli", "gaziantep", "adana",
         "kayseri", "denizli", "lira", "tl"),
        ("hürriyet", "hurriyet", "milliyet", "dünya", "dunya gazetesi",
         "ekonomim", "bloomberg ht", "anadolu", "sabah", "sözcü", "sozcu",
         "cumhuriyet", "birgün", "t24", "webrazzi", "patronlardunyasi"),
    ),
    Market(
        "Saudi Arabia", "SA", 1, "a Saudi publication",
        (Edition("ar-SA", "ar", "SA", "SA:ar", AR_QUERIES),
         Edition("en-SA", "en", "SA", "SA:en",
                 _en_anchored("Saudi", "Saudi Arabia", "Riyadh", "Jeddah", "NEOM"))),
        ("السعودية", "الرياض", "جدة", "الدمام", "saudi", "riyadh", "jeddah",
         "dammam", "neom", "aramco", "sabic", "الخبر", "مكة"),
        ("arab news", "argaam", "أرقام", "al arabiya", "العربية", "الاقتصادية",
         "aleqtisadiah", "saudi gazette", "asharq", "الشرق", "okaz", "عكاظ",
         "spa", "واس"),
    ),
    Market(
        "United Arab Emirates", "AE", 1, "a UAE publication",
        (Edition("ar-AE", "ar", "AE", "AE:ar", AR_QUERIES),
         Edition("en-AE", "en", "AE", "AE:en",
                 _en_anchored("UAE", "Dubai", "Abu Dhabi", "Emirates", "Sharjah"))),
        ("الإمارات", "دبي", "أبوظبي", "الشارقة", "uae", "dubai", "abu dhabi",
         "sharjah", "emirati", "emirates", "ajman", "ras al khaimah", "dirham"),
        ("the national", "gulf news", "khaleej times", "arabian business",
         "zawya", "البيان", "al bayan", "الاتحاد", "al ittihad", "emarat al youm",
         "wam", "وام", "gulf today"),
    ),
    Market(
        "Egypt", "EG", 1, "an Egyptian publication",
        (Edition("ar-EG", "ar", "EG", "EG:ar", AR_QUERIES),
         Edition("en-EG", "en", "EG", "EG:en",
                 _en_anchored("Egypt", "Egyptian", "Cairo", "Alexandria"))),
        ("مصر", "القاهرة", "الإسكندرية", "الجيزة", "egypt", "egyptian", "cairo",
         "alexandria", "giza", "suez", "جنيه", "egyptian pound"),
        ("al ahram", "الأهرام", "almasry alyoum", "المصري اليوم", "youm7",
         "اليوم السابع", "enterprise", "mada masr", "مدى مصر", "daily news egypt",
         "ahram online", "المال", "al mal", "amwal al ghad"),
    ),
    Market(
        "Pakistan", "PK", 1, "a Pakistani publication",
        (Edition("ur-PK", "ur", "PK", "PK:ur", (
            '"ملازمین کی برطرفی" OR "چھانٹی" OR "برطرفیاں" OR "عملہ کم"',
        )),
         Edition("en-PK", "en-PK", "PK", "PK:en",
                 _en_anchored("Pakistan", "Karachi", "Lahore", "Islamabad"))),
        ("pakistan", "pakistani", "karachi", "lahore", "islamabad", "rawalpindi",
         "faisalabad", "multan", "peshawar", "پاکستان", "کراچی", "لاہور",
         "rupee", "pkr"),
        ("dawn", "the express tribune", "business recorder", "the news international",
         "profit pakistan", "pakistan today", "arab news pakistan", "geo",
         "جنگ", "jang", "nation.com.pk"),
    ),
    Market(
        "Ukraine", "UA", 1, "a Ukrainian publication",
        (Edition("uk-UA", "uk", "UA", "UA:uk", (
            '"скорочення штату" OR "скорочення персоналу" OR "масові звільнення" '
            'OR "скорочення робочих місць"',
            '"закриття заводу" OR "припинення виробництва" (працівник OR персонал OR робочих)',
        )),
         Edition("ru-UA", "ru", "UA", "UA:ru", RU_QUERIES)),
        ("україн", "київ", "харків", "львів", "одес", "дніпр", "ukraine",
         "ukrainian", "kyiv", "kiev", "kharkiv", "lviv", "odesa", "dnipro",
         "гривн", "hryvnia"),
        ("epravda", "економічна правда", "ukrainska pravda", "українська правда",
         "interfax-ukraine", "kyiv independent", "kyiv post", "liga.net", "ліга",
         "nv.ua", "мінфін", "minfin", "forbes ukraine", "delo.ua"),
    ),
    Market(
        "Kazakhstan", "KZ", 1, "a Kazakh publication",
        (Edition("ru-KZ", "ru", "KZ", "KZ:ru", RU_QUERIES),
         Edition("kk-KZ", "kk", "KZ", "KZ:kk", (
             '"қызметкерлерді қысқарту" OR "штатты қысқарту" OR "жұмыстан босату"',
         ))),
        ("казахстан", "алматы", "астана", "нур-султан", "шымкент", "қазақстан",
         "kazakhstan", "kazakh", "almaty", "astana", "shymkent", "karaganda",
         "атырау", "тенге", "tenge"),
        ("tengrinews", "тенгриньюс", "kursiv", "курсив", "inbusiness",
         "zakon.kz", "informburo", "kapital.kz", "forbes.kz", "vlast.kz",
         "egemen", "khabar"),
    ),
    Market(
        "Colombia", "CO", 1, "a Colombian publication",
        (Edition("es-CO", "es-419", "CO", "CO:es-419", ES_QUERIES + (
            '"despidos" OR "recorte de personal" (Colombia OR Bogotá OR Medellín OR Cali)',
        )),),
        ("colombia", "colombian", "bogotá", "bogota", "medellín", "medellin",
         "cali", "barranquilla", "cartagena", "bucaramanga", "peso colombiano"),
        ("la república", "larepublica.co", "portafolio", "el tiempo",
         "el espectador", "semana", "valora analitik", "dinero", "el colombiano",
         "bluradio", "la silla vacía", "rcn"),
    ),
    Market(
        "Peru", "PE", 1, "a Peruvian publication",
        (Edition("es-PE", "es-419", "PE", "PE:es-419", ES_QUERIES + (
            '"despidos" OR "ceses colectivos" (Perú OR Lima OR Arequipa OR Trujillo)',
        )),),
        ("perú", "peru", "peruvian", "peruano", "lima", "arequipa", "trujillo",
         "callao", "chiclayo", "piura", "cusco", "sol peruano", "soles"),
        ("gestión", "gestion.pe", "el comercio", "la república", "larepublica.pe",
         "semana económica", "rpp", "infobae perú", "diario correo", "peru21",
         "andina"),
    ),
    Market(
        "Ghana", "GH", 1, "a Ghanaian publication",
        (Edition("en-GH", "en", "GH", "GH:en",
                 _en_anchored("Ghana", "Ghanaian", "Accra", "Kumasi", "Tema")),),
        ("ghana", "ghanaian", "accra", "kumasi", "tema", "takoradi", "tamale",
         "sekondi", "cedi", "ghs"),
        ("ghanaweb", "myjoyonline", "joy business", "citinewsroom", "citi news",
         "graphic online", "daily graphic", "b&ft", "business and financial times",
         "3news", "ghana business news", "asaaseradio", "the ghana report"),
    ),
    Market(
        "Morocco", "MA", 1, "a Moroccan publication",
        (Edition("fr-MA", "fr", "MA", "MA:fr", FR_QUERIES + (
            '"licenciements" OR "suppressions de postes" (Maroc OR Casablanca OR Tanger)',
        )),
         Edition("ar-MA", "ar", "MA", "MA:ar", AR_QUERIES)),
        ("maroc", "marocain", "morocco", "moroccan", "casablanca", "rabat",
         "marrakech", "tanger", "tangier", "agadir", "fès", "kénitra",
         "المغرب", "الدار البيضاء", "الرباط", "dirham"),
        ("medias24", "le matin", "l'economiste", "leconomiste", "telquel",
         "hespress", "هسبريس", "map", "maroc hebdu", "challenge.ma",
         "aujourd'hui le maroc", "la vie éco", "yabiladi", "le360"),
    ),
    Market(
        "Qatar", "QA", 1, "a Qatari publication",
        (Edition("ar-QA", "ar", "QA", "QA:ar", AR_QUERIES),
         Edition("en-QA", "en", "QA", "QA:en",
                 _en_anchored("Qatar", "Qatari", "Doha"))),
        ("qatar", "qatari", "doha", "قطر", "الدوحة", "lusail", "al rayyan",
         "qatari riyal"),
        ("gulf times", "the peninsula", "doha news", "al sharq", "الشرق",
         "al raya", "الراية", "qna", "قنا", "lusail news", "al watan qatar"),
    ),
    Market(
        "Kuwait", "KW", 1, "a Kuwaiti publication",
        (Edition("ar-KW", "ar", "KW", "KW:ar", AR_QUERIES),
         Edition("en-KW", "en", "KW", "KW:en",
                 _en_anchored("Kuwait", "Kuwaiti", "Kuwait City"))),
        ("kuwait", "kuwaiti", "الكويت", "kuwait city", "hawalli", "ahmadi",
         "kuwaiti dinar"),
        ("arab times", "kuwait times", "al qabas", "القبس", "al rai", "الراي",
         "al anba", "الأنباء", "kuna", "كونا", "al jarida", "الجريدة"),
    ),
    Market(
        "Sri Lanka", "LK", 1, "a Sri Lankan publication",
        (Edition("en-LK", "en", "LK", "LK:en",
                 _en_anchored("Sri Lanka", "Sri Lankan", "Colombo")),
         Edition("si-LK", "si", "LK", "LK:si", (
             '"සේවකයින් අඩු" OR "රැකියා අහිමි" OR "සේවයෙන් පහ"',
         )),
         Edition("ta-LK", "ta", "LK", "LK:ta", (
             '"பணிநீக்கம்" OR "வேலை இழப்பு" OR "ஊழியர் குறைப்பு"',
         ))),
        ("sri lanka", "sri lankan", "colombo", "kandy", "galle", "jaffna",
         "negombo", "gampaha", "katunayake", "sri lankan rupee", "lkr"),
        ("daily mirror", "dailymirror.lk", "daily ft", "ft.lk", "the island",
         "sunday times", "economynext", "ada derana", "adaderana", "newsfirst",
         "colombo gazette", "daily news lk", "the morning"),
    ),
    Market(
        "Serbia", "RS", 1, "a Serbian publication",
        (Edition("sr-RS", "sr", "RS", "RS:sr", (
            '"отпуштање радника" OR "otpuštanje radnika" OR "вишак запослених" '
            'OR "višak zaposlenih" OR "смањење броја запослених"',
            '"затварање фабрике" OR "zatvaranje fabrike" OR "остаје без посла" '
            'OR "ostaje bez posla" (радника OR radnika OR запослених OR zaposlenih)',
        )),),
        ("srbij", "србиј", "serbia", "serbian", "beograd", "београд", "belgrade",
         "novi sad", "нови сад", "niš", "ниш", "kragujevac", "крагујевац",
         "subotica", "dinar", "динар"),
        ("blic", "блиц", "danas", "данас", "politika", "политика", "n1",
         "nova ekonomija", "biznis.rs", "ekapija", "екапија", "b92", "rts",
         "vreme", "време", "nedeljnik"),
    ),

    # ---------------------------------------------------------------- tier 2
    # The alphabetical batch. Andorra is deliberately included AND deliberately
    # priced on its own: ~80k people means five feeds cost what Egypt's five
    # cost and return a fraction as many events. A visible zero row is part of
    # the design, but the yield-per-dollar has to be visible too.
    Market(
        "Afghanistan", "AF", 2, "an Afghan publication",
        (Edition("en-AF", "en", "AF", "AF:en",
                 _en_anchored("Afghanistan", "Afghan", "Kabul", "Herat", "Kandahar")),
         Edition("fa-AF", "fa", "AF", "AF:fa", (
             '"اخراج کارمندان" OR "بیکار شدن کارگران" OR "کاهش کارمندان"',
         ))),
        ("afghan", "afghanistan", "kabul", "herat", "kandahar", "mazar",
         "jalalabad", "kunduz", "afghani"),
        ("tolonews", "tolo news", "khaama", "pajhwok", "amu tv", "ariana news",
         "8am", "hasht e subh", "bakhtar news"),
    ),
    Market(
        "Albania", "AL", 2, "an Albanian publication",
        (Edition("sq-AL", "sq", "AL", "AL:sq", (
            '"largime nga puna" OR "pushime nga puna" OR "shkurtime vendesh pune" '
            'OR "shkurtim i stafit"',
            '"mbyllja e fabrikës" OR "falimentim" OR "fason" (punëtorë OR punonjës OR vende pune)',
        )),
         Edition("en-AL", "en", "AL", "AL:en",
                 _en_anchored("Albania", "Albanian", "Tirana"))),
        ("shqip", "shqipëri", "albania", "albanian", "tiranë", "tirana",
         "durrës", "durres", "vlorë", "vlora", "shkodër", "elbasan", "lek"),
        ("monitor.al", "balkan insight", "birn", "albanian daily news",
         "gazeta si", "a2 cnn", "abc news albania", "top channel", "scan tv",
         "shqiptarja", "panorama"),
    ),
    Market(
        "Algeria", "DZ", 2, "an Algerian publication",
        (Edition("fr-DZ", "fr", "DZ", "DZ:fr", FR_QUERIES + (
            '"licenciements" OR "dépôt de bilan" (Algérie OR Alger OR Oran)',
        )),
         Edition("ar-DZ", "ar", "DZ", "DZ:ar", AR_QUERIES)),
        ("algérie", "algerie", "algeria", "algerian", "algérien", "alger",
         "algiers", "oran", "constantine", "annaba", "blida", "sétif",
         "الجزائر", "dinar algérien"),
        ("algérie éco", "algerie eco", "tsa", "tsa-algerie", "maghreb émergent",
         "maghreb emergent", "el watan", "aps", "aps.dz", "l'expression",
         "liberté", "el khabar", "echorouk", "algerie360"),
    ),
    Market(
        "Andorra", "AD", 2, "an Andorran publication",
        (Edition("ca-AD", "ca", "AD", "AD:ca", (
            '"acomiadaments" OR "reducció de plantilla" OR "expedient de regulació" '
            'OR "tancament de l\'empresa"',
        )),),
        ("andorra", "andorrà", "andorrana", "andorran", "escaldes", "encamp",
         "la massana", "sant julià", "ordino", "canillo", "andorra la vella"),
        ("diari d'andorra", "diariandorra", "el periòdic d'andorra", "periodic.ad",
         "altaveu", "andorra difusió", "rtva", "bondia", "ara andorra"),
    ),
    Market(
        "Angola", "AO", 2, "an Angolan publication",
        (Edition("pt-AO", "pt-PT", "AO", "AO:pt-150", PT_QUERIES + (
            '"despedimentos" OR "reestruturação" (Angola OR Luanda OR Benguela)',
        )),),
        ("angola", "angolan", "angolano", "luanda", "benguela", "lobito",
         "huambo", "cabinda", "lubango", "kwanza"),
        ("expansão", "expansao", "mercado", "jornal de angola", "angop",
         "novo jornal", "o país", "o pais", "valor económico", "angola24horas",
         "rede angola"),
    ),
)

BY_COUNTRY = {m.country: m for m in MARKETS}
COUNTRIES = tuple(m.country for m in MARKETS)
