# -*- coding: utf-8 -*-
"""LORE's transcriber: Qwen3-ASR, gated by voice detection.

Called as a subprocess, exactly like ffmpeg and whisper-cli are, so nothing
heavy has to live inside the app itself:

    asr_worker.py <mix.wav> <output.json> [mic.wav]

3.31 READS BY SOURCE. The app names the Voice tap and the Game tap in the
environment (LORE_ASR_VOICE / LORE_ASR_GAME); the room is then the tap
plus his mic, the game is read off its own layer, and the Mix (still
argv[1]) becomes the MEDIA detector - see the block above main().

WHY THIS EXISTS. whisper has to choose ONE language for a stretch of audio and
then write everything in that language's alphabet. In a house where English and
Arabic land in the same sentence, that is fatal: "overhead" came back as
الوبرهد, and whole minutes collapsed into one word repeated seventy times.
Qwen3-ASR can hold both alphabets at once.

TWO THINGS MAKE OR BREAK IT, both learned the hard way:
  1. VOICE DETECTION FIRST. Give it silence and it invents words - "Wait." a
     hundred and sixty-three times. Silero decides what is speech; only speech
     is ever transcribed.
  2. A REPETITION PENALTY. Even on real speech it can run away inside a chunk.

Measured on his own recordings, worst run of one repeated word:
    English clip   163 -> 3
    Arabic clip     73 -> 3
and both of the sentences he quoted from memory came back verbatim.

2.84 ADDS A TRANSLITERATION WALL. The one thing this reader still gets
wrong that nothing else can catch is his own language: Emirati Gulf
Arabic written out in LATIN letters and tagged english, which the
Arabizi guard below never looks at (it only fires when the model SAYS
arabic). Those lines read as invented English proper nouns - "The Nefq?"
was promoted into two chapter titles as if it were real lore. See
_arabizi, and read its docstring before widening it: the obvious version
of this wall destroys correct English.

2.85 MAKES THAT WALL FACE THE OTHER WAY TOO. "هولي شت!" is him saying
HOLY SHIT with the sounds spelled out in ARABIC letters, and a wall
that only looks for Arabic-in-Latin never sees it - that line reached
the auditor's thread as Arabic speech. Both directions share one
trick: sound the words out into consonant classes and compare (see
_ar_fold / _en_fold), because vowels are exactly where two scripts
disagree. 2.85 also adds the one shape a word list can never catch -
a line that is laughter plus a single word nobody can read ("Zami
hehe.", which is زامي) - see _laughing_alone.
"""
import base64
import io
import json
import math
import os
import re
import sys
import time
import urllib.request

MODEL = os.environ.get("LORE_ASR_MODEL", "Qwen/Qwen3-ASR-1.7B-hf")
MIC_EXTRA_MAX = 60    # a stop on mic-only spans, not a budget
CHUNK_S = 28          # at most this much SPEECH per request
GROUP_GAP_S = 0.8     # speech separated by less than this is one utterance

# THE GPU ROUTE. When the app has a llama-server holding the same model as
# GGUF (measured 3.7x faster at parity quality on his own clips), it sets
# these and ask() talks to the server instead of loading torch weights.
# Unset, this file behaves exactly as it always has.
USE_GGUF = (os.environ.get("LORE_ASR_GGUF") or "").strip() in ("1", "true")
SERVER = (os.environ.get("LORE_ASR_SERVER")
          or "http://127.0.0.1:8908").rstrip("/")

# HOW MANY EXTRA REQUESTS ONE JOB MAY SPEND ON THE WALL BELOW. Measured
# over his whole library - 396 transcripts, 68,300 lines the model tagged
# non-Arabic and wrote in Latin letters - the wall fires 30 times in
# total, in 26 recordings, and never more than twice in one night. This
# is 12x the worst real night: it is not a budget, it is a stop so a
# night that goes wrong in some new way cannot spend an hour re-asking.
TRANSLIT_MAX = 24

# GULF WORDS NOTHING ENGLISH COLLIDES WITH. Every one of these was read
# off his own transcripts, in Latin letters, on a line the model had
# tagged english.
_ARABIZI_STRONG = frozenset("""
mafi mafee shu shoo shino shinu sheno wayed wayid waajid khalas
khallas halas yalla yallah yala akeed inzain shlonak shlonek shlon
habibi habeebi habibti habibna yaani yani laish laysh leish walla
wallah wallahi inshallah mashallah alhamdulillah astaghfirullah
nafaq nafag nefq nefg nafq sahm sahmani tabbi ehni ashwa
sowalef sowaleef fahamt fahemt shfeek shfeeh wesh mnu minu meno
khuth taal rooh agool gool gult mub mahu madri hatha hathi
hadhi hatheech haram ekhras iskit khalli khali shrayek yumma
yamma aiwa aywa sij abgha bagha yabi shwaya shway shofi shuf
shufu maku aku laken kaif kayf keef shbeek akhoi ukhti lazem lazim
shabab shabbab tamam mumkin bacher tawni ashan alashan
bisaraha mashkoor malish afwan tislam
hayak shakhbarak shakhbarek shhalak weinak weinik
""".split())

# THE SAME WORDS WHEN THEY ARE THE WHOLE LINE. "Yalla.", "Ah, Haram.",
# "Ya habibi." already read correctly to anyone who knows him; rewriting
# them in Arabic script buys nothing and costs a request. 68 of the
# first cut's 230 hits were exactly this and nothing else.
_ARABIZI_PLAIN = frozenset("""
yalla yallah yala habibi habeebi habibti habibna inshallah mashallah
alhamdulillah astaghfirullah haram wallah walla wallahi khalas khallas
halas shabab shabbab yani yaani akeed tamam aiwa aywa mashkoor afwan
tislam hayak ya la eh allah lazem lazim
""".split())

# Gulf, but also English words, people's names, or song noise ("oh la
# la", "bas bas bas"). One of these proves nothing on its own - they are
# here so the count of genuinely UNKNOWN words in a line comes out
# right.
_ARABIZI_WEAK = frozenset("""
fi feeh fee bas ana enta inta enti hatta shay shai kel kul kila
wain wein hena hnak sawi sawwi indi kida ilee elli illi min mn
zain zein abi chan haza la ya eh yaba khair kher marra mara
""".split())

# fillers and scaffolding that say nothing about which language a line
# is in - they survive inside an Arabic sentence and an English one
_ARABIZI_SKIP = frozenset("""
oh ah uh um eh haha hehe hah yeah yea ok okay hmm huh wow hey the
a an and or but no yes so like just man dude bro
""".split())

# THE ENGLISH THIS HOUSE ACTUALLY SPEAKS. One of these on the line and
# the wall stands down, and that single rule is what stops the wall
# turning "Alhamdulillah, the boss was last night again." into Arabic
# script. It is a blocker and only a blocker: a word missing from it
# costs one skipped re-ask, never a wrong transcript, so it is meant to
# be generous. Harvesting it from his own transcripts was tried and
# thrown away - the frequent "English" words it learned included mi, bi,
# dar, dam, zala and hiya, every one of them Arabic.
_ARABIZI_EN = frozenset("""
a about above across actually add after again against ah ahead all
almost alone along already alright also always am amazing among an and
angry animation another answer any anybody anyone anything anyway apart
are area aren't armor armour around arrive arrow as ask asked asking at
attack away awesome baby back bad bag ball base basically be beat
beautiful became because become bed been before began begin behind
being believe below beside best better between big bit black block
blocked blue boat body bomb book boom booms boots boss both bottom
bought bounce box boy boys break bring broke broken brother brought
buff build building built bullet burn bus but buy by bye call called
calling calm came camera can can't cannot car card cards care careful
carry case cash catch caught cause center chair champion chance change
chapter character charge chase chat cheap check chess chest chicken
chill choose ciao city claim clean clear click climb clip close closed
cold color combo come comes coming complete computer control cool copy
corner cost could couldn't count country couple course cover crazy
create crit cross cry current cut damage damn dance danger dark data
day dead deal death decide deck deep defence defend delete depends
design destroy device did didn't die died different difficult dig
dinner direct direction disconnect discord distance do does doesn't dog
doing dollar don't done door double down download drag draw dream drink
drive drop dropped drug dry duck due during dust each ear early earn
earth easily easy eat edge edit eight either else empty end enemy
energy engine enough enter entire episode escape especially even
evening event ever every everybody everyone everything exactly example
excited expect explain extra eye eyes face fact fail fall falling
family famous fan far fast faster fat father fault favorite favourite
fear feed feel feeling feet fell few field fight fighting figure file
fill film final finally find fine finger finish finished fire first
fish fit five fix fixed flag flash flat floor fly focus follow food
foot football for force forest forget forgot form forward found four
frame free freeze fresh friend friends from front fuck fucking full fun
funny future gain game games gap garden gas gate gave gear general get
gets getting gift girl girls give given giving glass go goal god goes
going gold gone good got gotta grab grabbed grabbing graphic graphics
grass great green grenade grey ground group grow guard guess guitar gun
guy guys had hair half hall hand handle hands happen happened happening
happy hard has hasn't hat hate have haven't having he he's head
headshot heal healer health hear heard heart heat heavy held hell hello
help her here hero herself hey hidden hide high hill him himself his
hit hold hole home honestly hope horse host hot hotel hour house how
however huge human hundred hungry hunt hurt i i'd i'll i'm i've ice
idea if image imagine immediately important impossible in insane inside
instead interest interesting into invite is island isn't issue it it's
item its itself jacket job join joined joke jump jumped just keep keeps
kept key keyboard kick kid kids kill killed killing kind king kitchen
knee knew knife knock know known lag land language large last late
later laugh launch lava lead leader learn least leave leaving led left
leg legend less let let's letter level library lie life lift light like
liked likely line link list listen little live load loading lobby local
lock long look looked looking looks loot lose loss lost lot loud love
low luck lucky lunch machine mad made magic mail main make makes making
man mana manage many map mark market master match material matter may
maybe me mean meaning means meant meet meeting member memory men
mention menu message met middle might mile milk mind mine minute
minutes miss missed missing mission mistake mix mob mode modern moment
money monster month months moon more morning most mother mount mouse
mouth move moved movement movie moving much music must my myself name
near nearly necessary neck need needs nerf never new news next nice
night nine no nobody noise none noob normal north nose not note nothing
notice now nowhere number obviously ocean of off offer office often oh
okay old on once one online only open opened opponent opposite or
orange order other others otherwise ought our out outside over own pack
package page pain paint pair paper parents park part particular party
pass passed past patch path pay peace people per perfect perhaps person
phase phone photo pick picked picture piece pinch ping pizza place plan
plane plant play played player players playing please plus point points
police poor pop portal position possible potion power practice prepare
present press pretty price print prize probably problem process product
project protect proud pull punch purple push put quality queen quest
question queue quick quickly quiet quit quite race radio ragdoll rage
rain raise ramp ran random range rank rare rate reach read ready real
really reason receive recent record red reduce refresh region release
reload remember remove repair repeat replay report respawn rest result
return review rich ride rifle right ring rise risk river road rock roll
roof room root round route row rule run running runs rush sad safe
safer said sail sale salt same sand sauce save saved saw say saying
says scale scary scene school score scream screen search season seat
second seconds secret section see seeing seem seems seen sell send
sense sent series serious serve server service session set settings
seven several shadow shake shall shape share sharp she she's sheet
shelf shield shine ship ships shirt shit shock shoe shoot shooting shop
short shot shotgun should shoulder shouldn't shout show showing shown
shut sick side sight sign silence silver similar simple simply since
sing single sink sir sister sit site situation six size skill skin sky
sleep slide slight slow slowly small smart smell smile smoke sniper
snow so social soft software sold soldier solid some somebody someone
something sometimes somewhere son song soon sorry sort sound south
space spaces spawn speak special speed spell spend spent spirit split
spot spray spring square stack staff stage stairs stand star stars
start started starting state station stay steal steam step stick still
stone stop stopped store storm story straight strange stream street
stress strike strong struggle stuck student study stuff stupid style
subject such sudden suddenly sugar suggest summer sun super support
suppose sure surface surprise survive sweat sweating sweet swim switch
sword system table tail take taken takes taking talk talking tall tank
tap target task taste tax tea teach team tears tech tell telling ten
terrible test text than thank thanks that that's the their them
themselves then there there's these they they'll they're thick thin
thing things think third thirty this those though thought thousand
three threw throne through throw throwing thrown thumb ticket tie tight
time times tiny tip tired title to today together told tomorrow tone
tonight too took tool top total touch tough tour toward tower town
track trade traffic train transfer trap travel tree trick tried trip
trouble truck true trust truth try trying tube turn turned turning
tutorial twelve twenty twice two type ugly under understand unit unless
unlock until up update upon upper us use used useful user using usually
value very video view village visit voice volume vote wait waiting wake
walk walking wall want wanted wants war warm warn was wasn't waste
watch watching water wave way we we'll we're we've weak wear weather
week weekend weight weird welcome well went were west what what's
whatever whatsapp wheel when where whether which while white who whole
whom whose why wide wife will win wind window wine wing winner winning
wins winter wipe wire wish with within without woman women won won't
wonder wood word words work worked working works world worry worse
worst worth would wouldn't wrong yard yeah year years yellow yes
yesterday yet you you'd you'll you're you've young your yours yourself
zone
""".split())


def _arabic_frac(t):
    """How much of the writing is in Arabic letters."""
    letters = sum(1 for c in t if c.isalpha())
    if not letters:
        return 0.0
    return sum(1 for c in t
               if "\u0600" <= c <= "\u06ff") / float(letters)


def _latin_frac(t):
    letters = sum(1 for c in t if c.isalpha())
    if not letters:
        return 0.0
    return sum(1 for c in t
               if "a" <= c.lower() <= "z") / float(letters)


def _arabizi(t):
    """Is this english-tagged line Gulf Arabic spelled in Latin letters?

    READ THIS BEFORE WIDENING IT. The re-ask this gates is pinned to
    Arabic, and pinning FORCES Arabic script - that is the trick the
    2.83 guard uses on purpose, and it means a wrong yes here does not
    fail safe: a correct English sentence comes back in Arabic letters,
    passes any "is it Arabic now" test, and replaces a good line.

    So the first cut of this function was measured line by line over his
    whole library and thrown out. It fired on 230 lines; about 180 of
    them were correct English carrying one loanword - "Yeah, they're
    grabbing me! Oh, seven left, Haram.", "Complete the tutorial to
    unlock Yalla.", "Alhamdulillah, the boss was last night again.".
    Every one would have been destroyed.

    What survives is three rules, in order of how much work they do:
      - ONE ENGLISH WORD AND THE WALL STANDS DOWN. An English sentence
        almost always contains one of _ARABIZI_EN; a Gulf one does not.
      - a line of nothing but stock transliterations ("Yalla.") is
        already right, so it never costs a request.
      - and beyond that, either every word is a Gulf word we KNOW
        ("The Nefq? Haha.", "Oh! Fi sahmani?"), or three or more of them
        are words no one can read at all ("Mafweerla alma kamsan? Ashan
        albarbaahein the listers."). Two unknown words next to a marker
        is the shape of "Yalla kina shotgun!" - a game noun, not Arabic
        - so that case is left alone unless the line is only two words
        long.

    Measured after all of that: 30 lines in 396 transcripts, in 26
    recordings, at most 2 in any one night, and reading all 30 there is
    not a correct English sentence among them. "The Nefq? Haha." is
    still in the set, which is the whole reason this exists.

    A digit-Arabizi rule ("3ala", "7abibi") was written and thrown away
    by the previous round: on his library it matched gt3, cs2, fp2, lmp2,
    ps3 and "3rd", and not one Arabic word. This reader spells words
    out, it does not write chat.

    2.85 TRIED TO REPLACE "unknown" (= not on my Gulf lists) WITH A
    REAL DICTIONARY - the CLAP text vocabulary the senses pass already
    ships - AND MEASURED IT LOSING. Both ways round, over his 63,881
    Latin lines:
      - as a COUNTER ("fire when one word is in no dictionary") it
        changes the verdict on exactly one line, and the wrong way:
        it holds back "Yalla, hamcho dam?", which is Arabic.
      - as a BLOCKER ("stand down if any word IS in the dictionary")
        it drops two lines this wall catches today, on "situ" and on
        "anti" - both of which the vocabulary lists as English words
        and both of which are Arabic here.
    Only 37 lines in the whole library even reach the count test, so
    there is nothing here for a dictionary to decide. It is used in
    exactly one place, _laughing_alone, where there is no Gulf marker
    to lean on and a word list is the thing that failed."""
    if not t or _latin_frac(t) < 0.9:
        return False
    body = [x for x in re.findall(r"[a-z']+", t.lower())
            if x not in _ARABIZI_SKIP]
    if not body or not any(x in _ARABIZI_STRONG for x in body):
        return False
    if any(x in _ARABIZI_EN for x in body):
        return False
    if all(x in _ARABIZI_PLAIN for x in body):
        return False
    unknown = {x for x in body if x not in _ARABIZI_STRONG
               and x not in _ARABIZI_WEAK}
    if len(unknown) >= 3 or not unknown:
        return True
    return len(unknown) == 1 and len(body) <= 2


# ===================================================================
#  2.85: THE WALL THE OTHER WAY ROUND, AND THE LINE WITH NO MARKER
# ===================================================================
# WHICH READER WROTE A TRANSCRIPT. A .stt.json is judged fresh by its
# timestamp alone, so a wall added today never reaches a night that was
# read yesterday - and nothing on disk said which reader had written a
# transcript, so there was no way even to ask. Every transcript carries
# this number now; the app counts them and says the number out loud.
READER = 6      # 5: the six-word echo band (see _ctx_echo); 6: the room
#                 off the Voice tap, media and game lines by source

# HOW MANY EXTRA REQUESTS THE TWO NEW WALLS MAY SPEND, the same
# reasoning as TRANSLIT_MAX: not a budget, a stop, so a night that goes
# wrong in some new way cannot spend an hour re-asking. Measured over
# his 397 transcripts (72,519 lines): the worst single night has ONE
# candidate for each wall. These are eight and six times that.
ENWALL_MAX = 8
LAUGH_MAX = 6

# 3.31 THE OTHER SOURCES. A 3.31 recording carries the room on its own
# tracks - the voice app's tap (Voice) and his mic - and the game on its
# own (Game); the device loopback (the Mix, still argv[1]) hears all of
# it plus whatever else the speakers played. Stops, not budgets, sized
# the way every other wall in this file is sized: a night that goes
# wrong in some new way cannot spend an hour reading a video.
MEDIA_SECS_MAX = 1800   # seconds of a video's speech one job may read
GAME_GROUPS_MAX = 120   # game utterances one job may read
# A source EXPLAINS a Mix span when it carries at least this much of the
# Mix's energy (1/4 amplitude = -12 dB). The process taps and the
# loopback share the same WASAPI mix gain (the probe measured a tone tap
# at -11 dBFS while its siblings sat silent), so a source that really
# carries a span sits within a few dB of the mix; 12 dB leaves 6+ dB of
# margin over ducking and normalisation and is far above a silent tap's
# floor. Reasoned, not yet measured on a real Discord+YouTube night.
MEDIA_RATIO = 0.25
MEDIA_FLOOR = 10 ** (-45 / 20.0)   # quieter than -45 dBFS is not speech worth attributing
# A Voice track this quiet over the WHOLE night, while the Mix carries a
# minute or more of speech nothing explains, was granted but hears
# nothing (Discord moved its audio process, a wrong root pid). It is not
# trusted: media detection stands down and those spans are read as the
# room, because friends must never be hidden as "a video".
DEAD_VOICE_DB = -60.0
MEDIA_CTX_DEFAULT = ("Narration or dialogue from a video, stream or song "
                     "playing in the background - not the people in the "
                     "room.")
GAME_CTX_DEFAULT = ("In-game dialogue, announcer and voice lines from the "
                    "game itself.")

# SOUNDING A WORD OUT. Each script folds to the same small alphabet of
# consonant classes and the vowels are thrown away, because vowels are
# where two scripts disagree most. Letters a listener could swap across
# the scripts share a class: Gulf ق is a g, and an English h in an
# Arabic mouth lands on ه ح خ, so all of them fold to K. "قولي الشط"
# folds to KLCT, and so does "holy shit".
_AR_CLASS = {}
for _ls, _cl in (("بپ", "B"),                # b p
                 ("تطث", "T"),               # t T th
                 ("جچهحخقكغ", "K"),          # j ch h H kh q k gh
                 ("دذضظ", "D"),              # d dh D DH
                 ("ر", "R"),
                 ("سصز", "S"),               # s S z
                 ("ش", "C"),                 # sh
                 ("فڤ", "F"),                # f v
                 ("ل", "L"), ("م", "M"), ("ن", "N")):
    for _c in _ls:
        _AR_CLASS[_c] = _cl

# MEASURED AND NOT DONE: folding د and ت together (an English "shit"
# written شد). It wins one true line, "هولي الشد كيف بين؟", and loses
# three ordinary Arabic ones to false alarms - "كلم اثناء؟" becomes
# "calm down", "يا رح أظهر..." becomes "right here". Net worse.

# one spelling per sound: the hamza seats and the alef maqsura are the
# same letter to a listener, and the marks are not letters at all
_AR_SAME = {"أ": "ا", "إ": "ا", "آ": "ا",
            "ى": "ي", "ؤ": "و", "ئ": "ي"}
# Arabic LETTERS only. The comma, semicolon and question mark live in
# the same Unicode block, and pulling them into words is not cosmetic:
# a trailing "؟" stops a word matching the common-word list below and
# lets a real Arabic line through the wall.
_AR_WORD = re.compile("[\u0621-\u063a\u0640-\u065f\u0670-\u06d3]+")


def _ar_plain(w):
    """One spelling per sound, and no vowel marks."""
    return "".join(_AR_SAME.get(c, c) for c in w
                   if not ("\u064b" <= c <= "\u065f") and c != "\u0640")


def _ar_fold(w):
    """Sound an Arabic word out into consonant classes."""
    w = _ar_plain(w)
    if len(w) > 3 and w.startswith("ال"):
        w = w[2:]              # "el-" is spelling, not a sound of its own
    while w and w[-1] in "هة":
        w = w[:-1]             # word-final h / ta marbuta is a vowel here
    out = []
    for c in w:
        k = _AR_CLASS.get(c)
        if k and (not out or out[-1] != k):
            out.append(k)
    return "".join(out)


_EN_PAIR = {"sh": "C", "ch": "C", "ph": "F", "th": "T", "ck": "K",
            "gh": "K", "wh": "", "kn": "N", "wr": "R", "qu": "K"}
_EN_ONE = {"b": "B", "p": "B", "t": "T", "d": "D", "j": "K", "g": "K",
           "k": "K", "q": "K", "x": "K", "h": "K", "c": "K", "s": "S",
           "z": "S", "f": "F", "v": "F", "l": "L", "m": "M", "n": "N",
           "r": "R"}


def _en_fold(w):
    """The same folding, for an English word."""
    w = w.lower()
    out, i = [], 0
    while i < len(w):
        if w[i:i + 2] in _EN_PAIR:
            k = _EN_PAIR[w[i:i + 2]]
            i += 2
        else:
            c = w[i]
            k = "S" if (c == "c" and w[i + 1:i + 2] in ("e", "i", "y")) \
                else _EN_ONE.get(c, "")
            i += 1
        if k and (not out or out[-1] != k):
            out.append(k)
    return "".join(out)


# THE ENGLISH HE ACTUALLY SHOUTS, and read the filter under it before
# adding anything. THROWN OUT AFTER MEASURING AGAINST ALL 7,189 OF HIS
# ARABIC LINES: "hold on" folds to KLDN and so does "يقوله دينو"; "are
# you serious" folds to RSRS and matched "ريسة ريسة" on two different
# nights. Both are ordinary Arabic and both would have been rewritten.
_EN_SAID = []
for _p in """holy shit|oh my god|oh my gosh|what the fuck|
what the hell|let's go|behind you|son of a bitch|well played|
what happened|oh my lord|for real|let him go|look at that|
that's crazy|i'm coming|help me|over here|right here|so close|
what the fuck is that|are you kidding me|shut the fuck up|
i can't believe|last one|calm down|go go go|thank you|watch out|
shut up|nice one|come on|oh shit|holy fuck|good game|good night
""".replace("\n", "").split("|"):
    _p = _p.strip()
    _sk = "".join(_en_fold(x) for x in _p.split())
    # TWO WORDS AND FOUR SKELETON LETTERS OR IT DOES NOT GO IN THE BOX.
    # A three-letter skeleton hits ordinary Arabic on sight: "nice one"
    # is NSN and so is "انزين ااا" (three of his nights), "come on" is
    # KMN and so is "ها منو". They stay in the list above because that
    # list is what he reads - this filter is what ships.
    if len(_p.split()) >= 2 and len(_sk) >= 4:
        _EN_SAID.append((_p, _sk))
_EN_SAID = tuple(_EN_SAID)

# ARABIC THAT IS NEVER PART OF AN ENGLISH PHRASE. A blocker, exactly
# like _ARABIZI_EN is a blocker on the other side: one of these inside
# the matched run and the wall stands down. A word missing from here
# costs one skipped re-ask, never a wrong transcript, so it is meant to
# be generous - and it is what kills three collisions on his library
# ("ها اللي فوق شو؟" as "holy fuck", "هذا النكتة..." as "good night",
# "هدق ما يستوي شيء..." as "good game").
_AR_COMMON = frozenset(_ar_plain(x) for x in """
هذا هذه هذي هاذي ذا ذي اللي الي انت انتي انتو انا احنا هو هي هم هن
في فيه فيها على علي من الى عن مع ما مو مب لا شو ايش وش وين ليش كيف
يعني والله الله ان اذا او بس كل كله كان يكون عند عندي عندك عنده
هنا هناك واحد شي شيء كده كذا ياخي يا اه ايه لي له لك بعد قبل تحت فوق
مال مالي حق عشان عقب بعدين خلاص تعال روح شوف اقول قال قلت لكن بعض
""".split())


def _english_head(t):
    """Does this Arabic line OPEN with an English phrase, sounded out?

    Returns (start, end, phrase) - the character span of the words that
    sounded it out - or None. Read this before widening it, the same
    way you read _arabizi: pinning the re-ask to English FORCES Latin
    letters, so the script of the answer proves nothing. Everything
    that decides lives here and in the confirmation test in _says.

    Three rules do all the work, and each one was measured over all
    7,189 Arabic-script lines in his library:
      - THE OPENING ONLY. Scanning anywhere in the line fires 14 times
        and 10 of those are ordinary Arabic caught mid-sentence. The
        exclamations he mixes in sit at the front. Anchored at the
        head: 4 hits.
      - EXACT, NEVER FUZZY, and at least two words and four skeleton
        letters (see the filter on _EN_SAID).
      - NOT ONE WORD OF ORDINARY ARABIC IN THE RUN (_AR_COMMON).
        Without it: 7 hits, 3 of them ordinary Arabic.

    What is left fires on 4 lines in 397 transcripts and every one of
    them really is English: "هولي شت!", "قولي الشط الصوت خراب!",
    "قولي شت ما شفته أنا...", "قولي شتي البطران؟" - all HOLY SHIT."""
    ws = list(_AR_WORD.finditer(t))
    if not ws:
        return None
    f = [_ar_fold(m.group(0)) for m in ws]
    # "يا" and "اه" carry no consonant of their own, so the head of the
    # line is the first word that does
    i = 0
    while i < len(ws) and not f[i]:
        i += 1
    for n in (2, 3, 4, 5):
        if i + n > len(ws):
            break
        if any(_ar_plain(m.group(0)) in _AR_COMMON for m in ws[i:i + n]):
            continue
        sk = "".join(f[i:i + n])
        for p, psk in _EN_SAID:
            if sk == psk:
                return (ws[i].start(), ws[i + n - 1].end(), p)
    return None


def _says(t, phrase):
    """Did the second reading say the phrase we suspected, in words?

    This is the whole safety of the reverse wall. The re-ask is pinned
    to English, so it comes back in Latin letters whatever was said -
    which means the ANSWER is only ever used as a yes or a no, never as
    text. A genuinely Arabic line pinned to English comes back as
    Arabizi ("el sot kharab"), which does not contain the phrase, and
    nothing changes."""
    def toks(s):
        return re.findall(r"[a-z]+", s.lower().replace("'", ""))
    a, b = toks(t), toks(phrase)
    if not b or len(a) < len(b):
        return False
    return any(a[i:i + len(b)] == b for i in range(len(a) - len(b) + 1))


def _load_en_dict():
    """A REAL English word list, for the one question a hand list
    cannot answer: is this word English AT ALL?

    The app already ships one - the CLAP text vocabulary the senses
    pass loads from the same folder. WHOLE WORDS ONLY (the entries
    marked with the leading space byte): the sub-word pieces in a BPE
    vocabulary include "aku", which is Gulf for "there is". Two-letter
    entries go too, for the same reason ("al", "wa", "bi", "li", "ma").
    Measured: 19,383 whole words, four of which are also on the Gulf
    lists (ana, bas, fee, min) and are taken back out below.

    Missing or unreadable, this returns nothing and _laughing_alone
    stands down completely - which is the safe answer, because without
    a dictionary the only test left is the hand list that missed
    "zami" in the first place."""
    p = os.environ.get("LORE_ASR_DICT") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models", "clap",
        "vocab.json")
    try:
        with open(p, encoding="utf-8") as fh:
            v = json.load(fh)
        pat = re.compile("\u0120[a-z]{3,}$")
        words = {k[1:] for k in v if pat.match(k)}
    except Exception:
        return frozenset()
    if len(words) < 4000:
        return frozenset()      # not the vocabulary we were promised
    words |= {x for x in _ARABIZI_EN if len(x) > 2}
    return frozenset(words - _ARABIZI_STRONG - _ARABIZI_PLAIN
                     - _ARABIZI_WEAK)


def _load_names():
    """Words the app has already told us about, so a NAME is not read
    as an unreadable word.

    A name is in no dictionary. The biasing context the app sets
    (LORE_ASR_CONTEXT) opens with "Gaming session of <the game>", so
    the game's own title is already here for nothing. Reading the typed
    voice names out of the .sns sidecars was written and thrown away:
    his whole library has three typed names in two files, and a wall
    that walks the sidecar folder to learn three words is not paying
    for itself."""
    raw = os.environ.get("LORE_ASR_CONTEXT") or ""
    return frozenset(x for x in re.findall(r"[a-z']+", raw.lower())
                     if len(x) > 2)


_EN_DICT = _load_en_dict()
_HIS_NAMES = _load_names()

# LAUGHTER, AND NOTHING THAT MERELY STARTS WITH AN H. The first cut of
# this read "hi", "he", "ho", "hu", "ham" and "hem" as laughs, which
# made "Hi <name>." a candidate for rewriting into Arabic. It now takes
# at least four letters, at least two h's, and a strict h-and-vowel
# alternation, so "huh", "hah", "heh", "hey", "ahem" and "hello" are
# all out and "hehe", "haha", "hoho", "ohhohoho" and the 23-letter
# "hahaha...hhaha" on his hearthstone night are all in.
_LAUGH_SHAPE = re.compile(r"^[aeiou]*(?:h+[aeiou]+)+h*$")
_LAUGH_WORD = re.compile(r"^(?:lol+|lmao+|hhh+)$")
# breath, not speech - these may share the line with a laugh and it is
# still a line with no English on it. "no", "yeah" and "okay" are NOT
# here on purpose: they are words, and a line carrying them is a line
# somebody was speaking English on.
_LAUGH_NOISE = frozenset("""
oh ah uh um eh hm hmm huh hah heh wow aha ooh aah ugh mm mmm oof
""".split())


def _is_laugh(w):
    return bool(_LAUGH_WORD.match(w)) or (
        len(w) >= 4 and w.count("h") >= 2 and bool(_LAUGH_SHAPE.match(w)))


def _laughing_alone(t):
    """Laughter, one word nobody can read, and nothing else at all.

    "Zami hehe." is زامي (a word on no list) plus a laugh, and no hand list
    will ever have "zami" on it - which is exactly why _arabizi cannot
    see this line: it demands a known Gulf marker before it will look.
    There is no marker here to lean on, so this leans on what IS here.
    Laughter reads the same in both languages, so a line of laughter
    plus ONE word that is in no dictionary, on no Gulf list, and not
    the game's own name has no English in it at all.

    On its own that is still not enough - the same shape catches
    "Haha! Dino." - so the caller also asks whether the room was
    speaking Arabic seconds either side.

    Measured over all 397 transcripts: 3 lines have the shape, and 2 of
    those also have Arabic within six seconds - "Zami hehe." and
    "Ruba! Haha.", both Arabic. Not one ordinary English line."""
    if not _EN_DICT or not t or _latin_frac(t) < 0.9:
        return False
    toks = re.findall(r"[a-z']+", t.lower())
    if not any(_is_laugh(x) for x in toks):
        return False
    body = [x for x in toks
            if not _is_laugh(x) and x not in _LAUGH_NOISE]
    if len(body) != 1 or len(body[0]) < 4:
        return False
    x = body[0]
    # a word we CAN read is not this wall's business either way: a Gulf
    # word already reads right, an English one is English
    return not (x in _EN_DICT or x in _HIS_NAMES or x in _ARABIZI_EN
                or x in _ARABIZI_STRONG or x in _ARABIZI_PLAIN
                or x in _ARABIZI_WEAK)


def _arabic_company(out, k, gap_s=6.0):
    """Was the room speaking Arabic on either side of this line?

    Seconds, not neighbours: an Arabic utterance three minutes later is
    not company, one two seconds later is the same exchange. On his
    library this is what separates "Zami hehe." (Arabic 2.4s later)
    from "Haha! Dino." (English both sides)."""
    sg = out[k]
    for j in (k - 1, k + 1):
        if not (0 <= j < len(out)):
            continue
        o = out[j]
        if _arabic_frac(o.get("t") or "") < 0.5:
            continue
        d = (sg["a"] - o["b"]) if j < k else (o["a"] - sg["b"])
        if d / 1000.0 <= gap_s:
            return True
    return False


# ===================================================================
#  THE FABRICATION GATES. At module level on purpose: the app lifts
#  these three by NAME out of this file to judge the transcripts that
#  were written before the gates existed (lore._fab_gates), so there
#  is exactly one definition of what a fabricated line is. A hand
#  copy in lore.py would drift - the strike migration learned that.
# ===================================================================

_CTX_STOP = frozenset(
    "the a an and or of in on with they we our your his her its it he "
    "she you i to for at by is are was were be this that".split())

def _ctx_echo(t, c):
    """Does this 'transcription' mostly restate the biasing context?

    On a thin, music-only utterance the model can regurgitate its own
    prompt as speech, embellished - a whole night was titled around a
    game nobody mentioned because the first "line" was the context
    paraphrased, with an invented favourite game stitched on. Compared
    on 4-letter word prefixes so 'gaming' still matches 'games'; seven
    content words minimum, so a real short callout ("let's play
    backrooms with friends on discord") never even costs the retry."""
    def toks(s):
        return [w for w in re.findall(r"[a-z']+", s.lower())
                if len(w) > 3 and w not in _CTX_STOP]
    # THE SHORT ARM. The seven-word floor below exempts exactly the
    # shape the library is full of: "Bloodthief." as a whole line,
    # nine times in one night nobody said it. A short line that
    # collapses to the game's own title (give or take one word) IS
    # the prompt speaking. Only the title clause is consulted -
    # never the boilerplate, whose words ("friends", "chat",
    # "discord") are ordinary speech in this house - and the remedy
    # is the same no-context retry as the long form, so a genuine
    # shout of the game's name survives by answering the same
    # words without the prompt.
    # the clause ends at the first period FOLLOWED BY WHITESPACE -
    # exactly how the builder terminates it - so a title with its
    # own periods ("R.E.P.O") survives the parse
    mg = re.match(r"\s*gaming session of (.+?)\.(?:\s|$)", c.lower())
    if mg:
        gt = re.findall(r"[a-z0-9']+", mg.group(1))
        lt = re.findall(r"[a-z0-9']+", t.lower())
        gj, lj = "".join(gt), "".join(lt)
        # the >=4 floor guards against one-letter accidents, but an
        # EXACT collapse match is the bare-title shape itself - a
        # shelf named "Ds" deserves the same guard as Bloodthief
        if (gj and (len(gj) >= 4 or gj == lj)
                and lt and len(lt) <= len(gt) + 1
                and len(lj) <= len(gj) + 8):
            # BOUNDARY-ALIGNED ONLY. The join exists so a split or
            # fused title still matches ("Blood thief." ~
            # "Bloodthief") - but without boundaries 'peak' hides
            # inside "don't speak" and a real line on a PEAK night
            # reads as the prompt leaking. A match must start and
            # end where a word starts or ends.
            bounds = {0}
            acc = 0
            for w in lt:
                acc += len(w)
                bounds.add(acc)
            k = lj.find(gj)
            while k != -1:
                if k in bounds and (k + len(gj)) in bounds:
                    return True
                k = lj.find(gj, k + 1)
    tw = toks(t)
    if len(tw) < 6:
        return False
    cp = {w[:4] for w in toks(c)}
    hit = sum(1 for w in tw if w[:4] in cp)
    # SIX WORDS NEED HALF. The seven-word floor let "Megabonk's
    # friends are chatting in the game while they play it." stand as
    # the ONLY line of a 77-minute night - and the describer named
    # the night from it. Measured over 99,712 lines: a six-word
    # band at >=0.5 adds exactly four lines, three of them the
    # prompt verbatim; the fourth costs one no-context re-ask, which
    # a real line survives. At seven and up the 0.4 bar is unchanged.
    return hit / float(len(tw)) >= (0.5 if len(tw) == 6 else 0.4)

def _impossible(t, secs):
    """More characters than a human mouth can make in the time.

    Real speech in this library: median 11.4 chars/sec, p99 26.8.
    Genuine in-game voice lines max at 16.0. The fabrications - the
    prompt paraphrased onto music, the "Oh yeah!" x27 attractor -
    run 78 to 263. Counted on speech characters only: whitespace,
    punctuation and Arabic tashkeel stripped (full diacritics
    inflate Arabic counts 40-90% and were the one measured
    collision risk), and judged by the SCRIPT actually written,
    never the language tag, because the tag lies."""
    if not t or secs <= 0:
        return False
    body = re.sub("[\u064B-\u0652\u0670]", "", t)
    body = "".join(ch for ch in body if ch.isalnum())
    if not body:
        return False
    letters = [ch for ch in body if ch.isalpha()]
    arab = sum(1 for ch in letters if "\u0600" <= ch <= "\u06ff")
    limit = 30.0 if letters and arab / float(len(letters)) > 0.5 \
        else 40.0
    return len(body) / float(secs) > limit

def _foreign(t):
    """Written in an alphabet nobody in this house uses? Only Latin
    and Arabic scripts may ship - the model wandered into CHINESE on a
    real night and the leash (which trusts the language TAG) never saw
    it, because the tag lied."""
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    ok = sum(1 for c in letters
             if ("a" <= c.lower() <= "z")
             or ("؀" <= c <= "ۿ")
             or ("ݐ" <= c <= "ݿ"))
    return ok / len(letters) < 0.5


# ===================================================================
#  3.31: THE ROOM, THE GAME, AND WHAT WAS PLAYING
# ===================================================================
# MEDIA IS DEFINED BY SUBTRACTION, never by content. The room's own
# speech spans (the Voice tap + the mic) and the game's are cut away from
# what the Mix heard FIRST; only a span that neither source carries any
# energy for is a video, a stream or a song. So a friend talking under a
# loud video stays the room, and a video is never quoted as a person.

def _load_layer(path, sr, sf, np, notes, name, n=None):
    """One extra layer (the Voice tap or the Game tap) as float32 mono at
    the mix's rate, or None with a note saying why it was skipped. With
    `n` (the mix's length in samples) the layer is trimmed or padded to
    it: every wav is ffmpeg's decode of the same mp4, so they agree to a
    frame, and more than half a second of drift is said out loud because
    lines past a short layer's end are then read from the mix and may
    include a video."""
    if not path or not os.path.isfile(path):
        return None
    try:
        x, xsr = sf.read(path, dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
    except Exception as e:
        notes.append(name + " layer skipped: " + str(e)[:80])
        return None
    if xsr != sr:
        notes.append(name + " layer skipped: rates differ (%d vs %d)"
                     % (xsr, sr))
        return None
    x = np.ascontiguousarray(x)
    if n is not None and len(x) != n:
        d = len(x) - n
        if abs(d) > 0.5 * sr:
            notes.append("the %s layer is %.1fs %s than the mix - the tail "
                         "is read from the mix"
                         % (name, abs(d) / float(sr),
                            "longer" if d > 0 else "shorter"))
        x = x[:n] if d > 0 else np.pad(x, (0, -d))
    return x


def _rms(arr, s0, e0):
    """Root-mean-square of one slice; 0.0 for an empty one."""
    seg = arr[s0:e0]
    if len(seg) == 0:
        return 0.0
    return float(math.sqrt(float((seg * seg).mean())))


def _subtract(spans, cover, sr, min_s=0.4, max_s=CHUNK_S):
    """Cut every `cover` interval away from every span; drop the pieces
    too short to be speech; split the ones longer than one request.
    Samples in, sorted (start, end) tuples out. This is the mic-extra
    cut lifted out of main() so the game and the media passes subtract
    the SAME way the mic always has (one subtraction, three callers)."""
    out = []
    cover = sorted(cover)
    for _x, _y in sorted(spans):
        if _x >= _y:
            continue
        _cuts = [(_x, _y)]
        for _mx, _my in cover:
            if _my <= _x or _mx >= _y:
                continue
            _nxt = []
            for _a2, _b2 in _cuts:
                if _mx > _a2:
                    _nxt.append((_a2, min(_b2, _mx)))
                if _my < _b2:
                    _nxt.append((max(_a2, _my), _b2))
            _cuts = [(p2, q2) for p2, q2 in _nxt if q2 - p2 > 0]
        for _a2, _b2 in _cuts:
            if _b2 - _a2 < min_s * sr:
                continue                  # too short to be speech
            while _b2 - _a2 > max_s * sr:
                out.append((_a2, _a2 + int(max_s * sr)))
                _a2 += int(max_s * sr)
            if _b2 - _a2 >= min_s * sr:
                out.append((_a2, _b2))
    return sorted(out)


def _media_spans(mixa, ra, ga, unexplained, sr):
    """Which of the Mix's unexplained speech spans are a VIDEO: the ones
    where neither the room nor the game carries MEDIA_RATIO of the Mix's
    energy, and the Mix itself stands over MEDIA_FLOOR. Returns (spans,
    why) - why names what was consulted, because without a Game track a
    span could as well be the game as a video."""
    out = []
    for s0, e0 in unexplained:
        m = _rms(mixa, s0, e0)
        if m < MEDIA_FLOOR:
            continue                      # quieter than -45 dBFS
        r = _rms(ra, s0, e0) if ra is not None else 0.0
        g = _rms(ga, s0, e0) if ga is not None else 0.0
        if r >= MEDIA_RATIO * m:
            continue                      # the room explains it
        if g >= MEDIA_RATIO * m:
            continue                      # the game explains it
        out.append((s0, e0))
    why = "mix>voice,game" if ga is not None else "mix>voice"
    return out, why


def _cap_seconds(spans, sr, max_s):
    """Keep the LONGEST spans up to max_s seconds of speech (the wall of
    MIC_EXTRA_MAX, by seconds instead of count) -> (kept sorted by start,
    dropped count, dropped seconds)."""
    kept, total = [], 0
    for s in sorted(spans, key=lambda s3: s3[1] - s3[0], reverse=True):
        n = s[1] - s[0]
        if total + n > max_s * sr:
            break
        kept.append(s)
        total += n
    whole = sum(e - s for s, e in spans)
    return sorted(kept), len(spans) - len(kept), (whole - total) / float(sr)


def _cap_count(spans, n_max):
    """Keep the n_max longest spans -> (kept sorted by start, dropped
    count, dropped seconds in samples/sr terms left to the caller)."""
    order = sorted(spans, key=lambda s3: s3[1] - s3[0], reverse=True)
    kept = sorted(order[:n_max])
    dropped = order[n_max:]
    return kept, len(dropped), sum(e - s for s, e in dropped)


def _sources_block(has_voice, has_game, media_ran, voice_s, mic_s, room_s,
                   game_s, media_s, media_read_s, game_read_s, stats):
    """The sidecar's 'sources' block: what this night carried by source,
    in seconds of Silero speech. Written AHEAD of the segments so the
    app's 8 KB head-read and the per-game ledger can read it cheaply.
    game_s is None when the night had no Game track (no vote, not zero)."""
    return {"v": 1, "voice": bool(has_voice), "game": bool(has_game),
            "media": bool(media_ran),
            "voice_s": round(float(voice_s), 1),
            "mic_s": round(float(mic_s), 1),
            "room_s": round(float(room_s), 1),
            "game_s": (round(float(game_s), 1) if has_game else None),
            "media_s": round(float(media_s), 1),
            "media_read_s": round(float(media_read_s), 1),
            "game_read_s": round(float(game_read_s), 1),
            "media_dropped": int(stats.get("media_dropped", 0)),
            "game_dropped": int(stats.get("game_dropped", 0)),
            "media_off": int(stats.get("media_off", 0))}


def _plan_sources(a, mixa, ga, spans, sr, vad, stats, notes, has_voice,
                  voice_db, media_on, game_lines_on):
    """THE SPLIT. `spans` are the room's speech spans as the VAD wrote
    them (dicts; the mic's extras already merged) over `a`, which is the
    room on a 3.31 night and the Mix itself on an old one. Decides what
    else the night carries - game speech the room does not cover, and
    the Mix speech that neither explains, a video - and returns
    (spans, media, game, meta): the room spans (with the dead-Voice
    guard's hand-backs, routed to the Mix by their 'mix' key), the media
    spans to read, the game spans to read, and the seconds of each for
    the sources block. `vad(arr)` -> [(start, end)] in samples. On an
    old file (no layers) it returns the spans it was given, untouched.
    Module level so the roster can drive it with a hand-made VAD."""
    room_spans = sorted((s["start"], s["end"]) for s in spans)
    room_s = sum(e - s for s, e in room_spans) / float(sr)
    has_game = ga is not None
    game_spans, game_s = [], 0.0
    if has_game:
        game_spans = _subtract(vad(ga), room_spans, sr)
        game_s = sum(e - s for s, e in game_spans) / float(sr)
    media, media_s, media_read_s, why = [], 0.0, 0.0, ""
    media_ran = False
    if (has_voice or has_game) and media_on:
        unexplained = _subtract(vad(mixa), room_spans + game_spans, sr)
        un_s = sum(e - s for s, e in unexplained) / float(sr)
        if has_voice and voice_db < DEAD_VOICE_DB and un_s >= 60:
            # THE HONESTY RULE: a tap that was granted but hears nothing
            # must not turn every friend into "a video" and hide them
            stats["media_off"] = 1
            notes.append("the Voice layer is silent for the whole night "
                         "while the mix carries %ds of speech - not "
                         "trusting it; those spans are read as the room"
                         % int(un_s))
            spans = sorted(list(spans) + [{"start": s, "end": e, "mix": 1}
                                          for s, e in unexplained],
                           key=lambda s3: s3["start"])
        else:
            media_ran = True
            media, why = _media_spans(mixa, a, ga, unexplained, sr)
            media_s = sum(e - s for s, e in media) / float(sr)
            if media:
                kept, dn, ds = _cap_seconds(media, sr, MEDIA_SECS_MAX)
                stats["media_dropped"] = dn
                media_read_s = sum(e - s for s, e in kept) / float(sr)
                notes.append("the video layer found %d span(s), %ds of "
                             "speech" % (len(media), int(media_s))
                             + ((" - the wall keeps the longest %ds, %ds "
                                 "went unread" % (MEDIA_SECS_MAX, int(ds)))
                                if dn else ""))
                media = kept
    game_read, game_read_s = [], 0.0
    if has_game and game_spans:
        if game_lines_on:
            game_read, dn, dsm = _cap_count(game_spans, GAME_GROUPS_MAX)
            stats["game_dropped"] = dn
            game_read_s = sum(e - s for s, e in game_read) / float(sr)
            notes.append("the game spoke for %ds in %d span(s)"
                         % (int(game_s), len(game_spans))
                         + ((" - the wall keeps the %d longest, %d went "
                             "unread" % (GAME_GROUPS_MAX, dn)) if dn else ""))
        else:
            notes.append("the game spoke for %ds in %d span(s) - counted, "
                         "not read" % (int(game_s), len(game_spans)))
    meta = {"room_s": room_s, "game_s": game_s, "media_s": media_s,
            "media_read_s": media_read_s, "game_read_s": game_read_s,
            "why": why, "media_ran": media_ran}
    return spans, media, game_read, meta


def _group_spans(span_list, arr_of, sr, kind):
    """Neighbouring speech into requests, remembering the REAL times so
    the transcript still lines up with the video. The 3.1x grouping
    loop, lifted out so one routine serves three sources: `arr_of(span)`
    -> (audio slice, mic samples) is how a span's audio is fetched (the
    clean mic or the room for room spans, the Mix for media, a COPY of
    the game layer for game spans so the layer can be released)."""
    groups, cur = [], None
    for s in span_list:
        piece, micn = arr_of(s)
        if cur and (s["start"] - cur["end"]) / sr <= GROUP_GAP_S \
                and (cur["len"] + s["end"] - s["start"]) <= sr * CHUNK_S:
            cur["parts"].append(piece)
            cur["len"] += s["end"] - s["start"]
            cur["mic"] += micn
            cur["end"] = s["end"]
        else:
            if cur:
                groups.append(cur)
            cur = {"parts": [piece, ], "start": s["start"],
                   "end": s["end"], "len": s["end"] - s["start"],
                   "mic": micn, "kind": kind}
    if cur:
        groups.append(cur)
    return groups


def main(src, dst, mic=None):
    import numpy as np
    import soundfile as sf
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    # HOW MUCH OF THE MACHINE THIS MAY TAKE, AND IT CAN CHANGE ITS MIND.
    # The app writes a number beside the wav and rewrites it whenever the
    # situation changes; we re-read it between utterances. Deciding once at
    # launch meant a game closed twenty minutes ago still cost three quarters
    # of the processor, for the whole rest of the job.
    ctl_path = src + ".ctl"
    default_threads = max(2, (os.cpu_count() or 8) - 4)

    def wanted_threads():
        try:
            with open(ctl_path, encoding="utf-8") as fh:
                n = int(json.load(fh).get("threads") or 0)
            if n > 0:
                return max(1, min(n, os.cpu_count() or n))
        except Exception:
            pass
        try:
            return max(1, int(os.environ.get("LORE_ASR_THREADS") or 0)) \
                if os.environ.get("LORE_ASR_THREADS") else default_threads
        except ValueError:
            return default_threads

    have_threads = [0]

    def apply_threads():
        n = wanted_threads()
        if n != have_threads[0]:
            torch.set_num_threads(n)
            have_threads[0] = n
        return n

    apply_threads()

    # WHERE IT HAS GOT TO, in a file. Printing it was useless: the app reads
    # this pipe with communicate(), which returns only once the process has
    # exited, so not one of those lines was ever seen while it mattered.
    prog_path = src + ".prog"
    _room_s = [0.0]       # seconds of the ROOM's speech, once it is known

    def say_progress(done, total, secs_done, secs_total):
        try:
            tmp = prog_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"done": done, "total": total,
                           "audio_done": round(secs_done, 1),
                           "audio_total": round(secs_total, 1),
                           "room_s": round(_room_s[0], 1),
                           "threads": have_threads[0]}, fh)
            os.replace(tmp, prog_path)
        except Exception:
            pass
    a, sr = sf.read(src, dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != 16000:
        # the contract is 16 kHz mono from the app's own ffmpeg; anything
        # else means the wrong file reached us - refuse rather than feed
        # the voice detector audio at a rate it will mishear
        raise SystemExit(f"expected 16000 Hz input, got {sr}")
    engine = "qwen3-asr-gguf" if USE_GGUF else "qwen3-asr"
    # how often the guards fired - the app logs one summary line per job
    stats = {"arabizi": 0, "leash": 0, "echo": 0, "translit": 0,
             "translit_won": 0, "mic_lines": 0, "enwall": 0,
             "enwall_won": 0, "laugh": 0, "laugh_won": 0,
             "physics": 0, "leash_kept": 0, "mic_only": 0,
             "mic_dropped": 0,
             # 3.31 by source: lines filed to a video / the game, what the
             # walls left unread, and whether the dead-Voice guard fired
             "media_lines": 0, "game_lines": 0, "media_dropped": 0,
             "game_dropped": 0, "media_off": 0}
    # AND WHAT ELSE HAPPENED, in words. These used to go to stderr, which
    # the app only reads when the job FAILS - so a mic layer that quietly
    # skipped itself left no trace anywhere on a successful run.
    notes = []
    # 3.31 THE OTHER LAYERS COME BY ENVIRONMENT. argv[1] stays the Mix -
    # the .ctl and .prog files are keyed on it - and the app names the
    # Voice tap and the Game tap beside it. Absent, this is exactly the
    # 3.1x reader: the mix is the room and nothing below runs.
    voice = os.environ.get("LORE_ASR_VOICE") or ""
    game = os.environ.get("LORE_ASR_GAME") or ""
    ctx_media = ((os.environ.get("LORE_ASR_CONTEXT_MEDIA") or "").strip()
                 or MEDIA_CTX_DEFAULT)
    ctx_game = ((os.environ.get("LORE_ASR_CONTEXT_GAME") or "").strip()
                or GAME_CTX_DEFAULT)
    media_on = (os.environ.get("LORE_ASR_MEDIA") or "1") != "0"
    game_lines_on = (os.environ.get("LORE_ASR_GAME_LINES") or "1") != "0"

    say_progress(0, 0, 0.0, len(a) / float(sr))    # "started, finding speech"

    # HIS VOICE COMES OFF HIS OWN MICROPHONE. The clean Mic track has
    # ridden beside the mix since 2.81 and was only ever used to TAG
    # lines after the fact. Its voice detector now runs FIRST, and every
    # speech span it claims is sliced from the clean audio instead of
    # the mix - same number of model calls, the noise floor gone from
    # his half of the night. Friends and the game stay on the mix,
    # which is the only place they exist. (3.31: opened before the room
    # is built, because the room is the Voice tap PLUS this.)
    ma, mm = None, []
    if mic and os.path.isfile(mic):
        try:
            ma, msr = sf.read(mic, dtype="float32")
            if ma.ndim > 1:
                ma = ma.mean(axis=1)
            if msr != sr:
                notes.append("mic routing skipped: rates differ "
                             f"({msr} vs {sr})")
                ma = None
            else:
                mspans = get_speech_timestamps(
                    torch.from_numpy(np.ascontiguousarray(ma)),
                    load_silero_vad(), sampling_rate=sr,
                    min_silence_duration_ms=300, speech_pad_ms=120)
                mm = [(s2["start"], s2["end"]) for s2 in mspans]
        except Exception as e2:
            notes.append("mic routing skipped: " + str(e2)[:80])
            ma = None

    def _vad_tuples(arr):
        """The mix VAD's exact call over another layer -> [(s, e)]."""
        return [(s3["start"], s3["end"]) for s3 in get_speech_timestamps(
            torch.from_numpy(np.ascontiguousarray(arr)), load_silero_vad(),
            sampling_rate=sr, min_silence_duration_ms=300,
            max_speech_duration_s=CHUNK_S, speech_pad_ms=200)]

    # 3.31 THE ROOM. VOICE = the voice app's tap + his mic: the tap does
    # not carry his own voice, so a shared span sliced from the tap alone
    # would erase his half - summing the mic in keeps today's behaviour
    # for overlaps (the 0.9 rule below still routes his solo spans to
    # the clean mic). Sample alignment holds because every wav is
    # ffmpeg's 16 kHz decode of the same mp4. With a Game tap but no
    # Voice (a by-source night with the voice app closed) the room is
    # his mic alone; with neither, the mix is the room, as it always was.
    mixa = a                          # the device loopback, kept by name
    va = _load_layer(voice, sr, sf, np, notes, "voice", len(a))
    ga = _load_layer(game, sr, sf, np, notes, "game", len(a))
    has_voice = va is not None
    has_game = ga is not None
    voice_lost = bool(voice) and not has_voice
    if voice_lost and media_on:
        # THE APP NAMED A VOICE LAYER AND IT WOULD NOT LOAD. With a Game
        # tap beside it the room would be the mic alone and every friend
        # in the Mix would be filed as "a video" and folded away - the
        # honesty rule again: no room, no media verdict, and the mix is
        # the room (the reader-hears-the-mix rung), exactly as before.
        media_on = False
        notes.append("the Voice layer could not be loaded - media "
                     "detection stood down")
    voice_db, voice_s = -120.0, 0.0
    if has_voice:
        _vr = _rms(va, 0, len(va))
        voice_db = 20.0 * math.log10(_vr) if _vr > 0 else -120.0
        # seconds of speech on the Voice tap ALONE - the ledger's
        # "does this game carry voice chat" reads this number
        voice_s = sum(e - s for s, e in _vad_tuples(va)) / float(sr)
        if ma is not None:
            _n = min(len(va), len(ma))
            va[:_n] += ma[:_n]
            np.clip(va, -1.0, 1.0, out=va)
        a = va
        del va
    elif has_game and ma is not None and not voice_lost:
        a = ma                        # the room is his mic alone tonight

    _mix_spans_first = True
    spans = get_speech_timestamps(torch.from_numpy(a), load_silero_vad(),
                                  sampling_rate=sr,
                                  min_silence_duration_ms=300,
                                  max_speech_duration_s=CHUNK_S,
                                  speech_pad_ms=200)
    # A SILENT MIX IS NOT A SILENT NIGHT. This used to end the job
    # here - before the microphone was ever opened, four lines below -
    # so a night where the game was quiet and he was the only one
    # talking transcribed to nothing at all. 225 recordings on the
    # shelf logged "0 lines". The mic gets its say before anything is
    # given up on; if it has nothing either, the answer is the same.
    # (3.31: nor is a silent ROOM - the mix may still carry a video,
    # and the game tap its lines; the ledger wants the block regardless.)
    if not spans and not (mic and os.path.isfile(mic)) \
            and not ((has_voice or has_game) and media_on) \
            and not has_game:
        json.dump({"sources": _sources_block(
                       has_voice, has_game, False, voice_s, 0.0, 0.0,
                       0.0, 0.0, 0.0, 0.0, stats),
                   "segments": [], "model": MODEL, "engine": engine,
                   "reader": READER, "counters": stats},
                  open(dst, "w", encoding="utf-8"))
        say_progress(0, 0, 0.0, 0.0)
        return 0

    def _span_audio(s):
        """(slice, mic-samples): the clean mic when its own detector
        says these samples carry his voice, the room (or mix) otherwise."""
        s0, e0 = s["start"], s["end"]
        if s.get("mix"):
            return mixa[s0:e0], 0     # handed back by the dead-Voice guard
        if ma is not None and e0 <= len(ma):
            ov = 0
            for x, y in mm:
                if x >= e0:
                    break
                ov += max(0, min(e0, y) - max(s0, x))
            # 0.9, NOT 0.4: the mix VAD merges overlapping voices into
            # one span, and friends exist ONLY on the mix - routing a
            # shared span to the mic would erase whoever talked over
            # him. Only a span the mic covers essentially end-to-end is
            # safely his alone. TAGGED, NEVER FILTERED still holds.
            if ov >= 0.9 * max(1, e0 - s0):
                return ma[s0:e0], e0 - s0
        return a[s0:e0], 0

    # HIS VOICE CAN START A LINE. The mic detector used to be allowed
    # only to ROUTE inside spans the mix had already found, so a
    # sentence the mix missed under a loud game - or under three
    # friends at once - was never a candidate at all, however clean
    # the mic had it. Its spans join the mix's here: subtracted first
    # so nothing is decoded twice, fragments too short to be speech
    # dropped, anything longer than one request split (_subtract - the
    # one cut the game and media passes share).
    if ma is not None and mm:
        _mix = sorted((s3["start"], s3["end"]) for s3 in spans)
        _mm = []
        for _x, _y in sorted(mm):
            # never past the end of EITHER track: a mic recording that
            # outruns the mix would otherwise put a line past the end
            # of the video
            _y = min(_y, len(ma), len(a))
            if _x >= _y:
                continue
            _mm.append((_x, _y))
        _extra = [{"start": _a2, "end": _b2}
                  for _a2, _b2 in _subtract(_mm, _mix, sr)]
        # A STOP, NOT A BUDGET - the same rule the other three walls
        # in this file carry, and this one adds whole model requests
        # rather than cheap re-asks. The longest spans are kept: those
        # are the ones most likely to be speech rather than a noisy
        # floor.
        _found = len(_extra)
        if _found > MIC_EXTRA_MAX:
            _extra.sort(key=lambda s3: s3["end"] - s3["start"],
                        reverse=True)
            _extra = sorted(_extra[:MIC_EXTRA_MAX],
                            key=lambda s3: s3["start"])
            stats["mic_dropped"] = _found - MIC_EXTRA_MAX
        if _extra:
            stats["mic_only"] = len(_extra)
            # THE NUMBER IT FOUND, NOT THE NUMBER IT KEPT. This said
            # "found 60" on a night where it had found far more, and
            # what was lost was recorded nowhere at all.
            notes.append(
                "the mic found %d span(s) the mix had missed"
                % _found
                + ("" if _found <= MIC_EXTRA_MAX else
                   " - the wall keeps the %d longest, %d went unread"
                   % (MIC_EXTRA_MAX, _found - MIC_EXTRA_MAX)))
            spans = sorted(list(spans) + _extra,
                           key=lambda s3: s3["start"])

    # 3.31 THE SPLIT: what else this night carries (nothing, on an old
    # file - the spans come back untouched)
    mic_s = sum(y - x for x, y in mm) / float(sr)
    spans, media_spans, game_spans, smeta = _plan_sources(
        a, mixa, ga, spans, sr, _vad_tuples, stats, notes, has_voice,
        voice_db, media_on, game_lines_on)
    _room_s[0] = smeta["room_s"]

    # group neighbouring speech into requests, remembering the REAL times so
    # the transcript still lines up with the video - one routine, three
    # sources; the game slices are COPIES so the layer can be released
    # (120 x 28 s x 64 KB = 215 MB at most against a fourth full array)
    groups = _group_spans(spans, _span_audio, sr, "room")
    groups_media = _group_spans(
        [{"start": s3, "end": e3} for s3, e3 in media_spans],
        lambda s: (mixa[s["start"]:s["end"]], 0), sr, "media")
    groups_game = _group_spans(
        [{"start": s3, "end": e3} for s3, e3 in game_spans],
        lambda s: (np.array(ga[s["start"]:s["end"]]), 0), sr, "game")
    del ga

    # WHAT THIS AUDIO IS. Qwen3-ASR takes a free-text biasing context - the
    # app passes the game's name and the register of the room (friends on
    # Discord, Emirati Arabic and English mid-sentence). Without it the model
    # transcribes each utterance as if it fell out of the sky.
    ctx = (os.environ.get("LORE_ASR_CONTEXT") or "").strip() or None
    # 3.31: the media and game passes bias with their OWN context (a
    # video is not "friends on Discord"), and _ctx_echo must compare
    # against the context that was actually sent - so ask() reads it
    # through this one cell instead of the name above
    cur_ctx = [ctx]

    if USE_GGUF:
        # ---- the GPU: llama-server (llama.cpp mtmd) ---------------------
        # Mirrors the HF recipe exactly: context is the system message, the
        # user turn is the audio alone, and forcing a language is done by
        # prefilling the assistant turn with "language <Name><asr_text>"
        # (the server continues a trailing assistant message, and the
        # KV-cache makes that retry nearly free).
        def ask_raw(audio, language, use_ctx=True):
            buf = io.BytesIO()
            sf.write(buf, audio, sr, format="WAV", subtype="PCM_16")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            msgs = []
            if cur_ctx[0] and use_ctx:
                msgs.append({"role": "system", "content": cur_ctx[0]})
            msgs.append({"role": "user", "content": [
                {"type": "input_audio",
                 "input_audio": {"data": b64, "format": "wav"}}]})
            if language:
                msgs.append({"role": "assistant",
                             "content": "language %s<asr_text>"
                                        % language.capitalize()})
            body = {"messages": msgs, "temperature": 0, "max_tokens": 440,
                    "repeat_penalty": 1.15, "repeat_last_n": 64}
            req = urllib.request.Request(
                SERVER + "/v1/chat/completions",
                json.dumps(body).encode("utf-8"),
                {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=600) as resp:
                j = json.load(resp)
            ch = (j.get("choices") or [{}])[0]
            raw = (ch.get("message") or {}).get("content") or ""
            cut = ch.get("finish_reason") == "length"
            if "<asr_text>" in raw:
                lang = (re.search(r"language\s+([A-Za-z]+)\s*<asr_text>",
                                  raw) or [None, ""])[1]
            else:
                # prefilled reply: the prefix lived in the prefill
                return raw.strip(), (language or "").lower(), cut
            m = re.search(r"<asr_text>(.*)", raw, re.S)
            return (m.group(1) if m else raw).strip(), lang.lower(), cut

        def ask(audio, language, use_ctx=True):
            txt, lang, cut = ask_raw(audio, language, use_ctx)
            if cut and len(audio) > sr * 4:
                # the reply hit the 440-token ceiling and was cut
                # mid-sentence (a dense bilingual 28s chunk can overrun it):
                # transcribe the halves instead - recursion bottoms out at 4s
                mid = len(audio) // 2
                t1, l1 = ask(audio[:mid], language, use_ctx)
                t2, l2 = ask(audio[mid:], language or l1, use_ctx)
                if (t1 + t2).strip():
                    return (t1 + " " + t2).strip(), (l1 or l2)
            # THE ARABIZI GUARD. In 2 of 8 A/B clips the GGUF path wrote a
            # whole Arabic utterance in Latin letters. When the model itself
            # says Arabic but the script says otherwise, ask again with the
            # language pinned and keep whichever answer is actually written
            # in Arabic.
            if lang == "arabic" and txt and len(txt) > 8 \
                    and _arabic_frac(txt) < 0.15:
                stats["arabizi"] += 1
                t2, l2, _c = ask_raw(audio, "arabic", use_ctx)
                if t2 and _arabic_frac(t2) > _arabic_frac(txt):
                    txt, lang = t2, (l2 or "arabic")
            return txt, lang
    else:
        # ---- the CPU: torch weights, exactly as it always was -----------
        # the model ships with the app - prefer the copy on disk, and only
        # touch the network if it is genuinely absent (never for a "newer"
        # upstream revision that could change behaviour under him)
        from transformers import (Qwen3ASRForConditionalGeneration,
                                  Qwen3ASRProcessor)
        try:
            proc = Qwen3ASRProcessor.from_pretrained(
                MODEL, local_files_only=True)
            mdl = Qwen3ASRForConditionalGeneration.from_pretrained(
                MODEL, dtype=torch.float32, local_files_only=True).eval()
        except Exception as e:
            # the model ships with the app - a missing local copy used to
            # trigger a SILENT multi-GB download from the network (or an
            # offline hang). Fail loudly instead; downloads only when
            # deliberately asked for.
            if (os.environ.get("LORE_ASR_ALLOW_FETCH") or "") != "1":
                raise SystemExit(
                    f"the shipped model is missing or unreadable ({e}); "
                    f"set LORE_ASR_ALLOW_FETCH=1 to fetch it from the "
                    f"network deliberately") from e
            proc = Qwen3ASRProcessor.from_pretrained(MODEL)
            mdl = Qwen3ASRForConditionalGeneration.from_pretrained(
                MODEL, dtype=torch.float32).eval()

        def ask(audio, language, use_ctx=True):
            inp = proc.apply_transcription_request(
                audio=audio, language=language,
                prompt=(cur_ctx[0] if use_ctx else None), sampling_rate=sr,
                return_tensors="pt")
            with torch.no_grad():
                ids = mdl.generate(**inp, max_new_tokens=440,
                                   repetition_penalty=1.15,
                                   no_repeat_ngram_size=8)
            gen_n = ids.shape[-1]
            try:
                gen_n = ids.shape[-1] - inp["input_ids"].shape[-1]
            except Exception:
                pass
            if gen_n >= 438 and len(audio) > sr * 4:
                # hit the token ceiling = cut mid-sentence; halves instead
                mid = len(audio) // 2
                t1, l1 = ask(audio[:mid], language, use_ctx)
                t2, l2 = ask(audio[mid:], language or l1, use_ctx)
                if (t1 + t2).strip():
                    return (t1 + " " + t2).strip(), (l1 or l2)
            raw = proc.batch_decode(ids, skip_special_tokens=True)[0]
            # the reply announces its choice: "language English<asr_text>..."
            lang = (re.search(r"language\s+([A-Za-z]+)\s*<asr_text>",
                              raw) or [None, ""])[1]
            m = re.search(r"<asr_text>(.*)", raw, re.S)
            return (m.group(1) if m else raw).strip(), lang.lower()

    # THESE TWO ARE THE ONLY LANGUAGES IN THIS HOUSE. The model knows 52 and
    # picks per utterance, so a short or noisy one comes back as Dutch, Malay,
    # Persian or Chinese - all of which it produced on a real recording. When
    # it wanders, ask again and hold it to whatever was being spoken a moment
    # ago, because people do not change language between one breath and the
    # next nearly as often as this model thinks.
    KEEP = ("english", "arabic")

    # _CTX_STOP, _ctx_echo, _impossible and _foreign live at module
    # level now - THE FABRICATION GATES, above main()
    speech_total = (sum(g["len"] for g in groups)
                    + sum(g["len"] for g in groups_media)
                    + sum(g["len"] for g in groups_game)) / float(sr)
    n_all = len(groups) + len(groups_media) + len(groups_game)
    speech_done = 0.0
    out, last = [], "english"
    # WHICH UTTERANCE EACH LINE CAME FROM. The laughter wall below can
    # only judge a line once the whole night is on the page (it asks
    # what was said either side of it, and "Zami hehe." is given away
    # by the line AFTER it), and by then the loop has moved on - so it
    # needs a way back to the audio. groups[] is already in memory and
    # its parts are views into the same array, so this costs a list of
    # integers and nothing else.
    gidx = []
    slow_n = [0]

    def _read(audio, walls, secs):
        """One utterance through the model and every fabrication gate
        -> (txt, lang, lost). The leash, the foreign-alphabet test, the
        echo test and the physics test always run; the HOUSE walls -
        Arabizi (inside ask), Arabic-in-Latin, English-in-Arabic - only
        with walls=True, because they exist for Emirati speech and would
        spend their stops on a video or a game's announcer. `last`
        learns from every line that ships; the passes that must not
        teach it a video's language save and restore it around the
        call."""
        nonlocal last
        ctx = cur_ctx[0]         # the context THIS pass is sending
        t_ask = time.time()
        lost = None
        txt, lang = ask(audio, None)
        if lang and lang not in KEEP:
            stats["leash"] += 1
            if not out:
                # the FIRST utterance has no history to hold it to: pin by
                # the SCRIPT of what it actually wrote - an Arabic night
                # opened by one wandering guess used to get pinned English
                letters = sum(1 for c in txt if c.isalpha())
                arab = sum(1 for c in txt if "\u0600" <= c <= "\u06ff")
                last = ("arabic" if letters and arab / float(letters) > 0.3
                        else "english")
            # THE RETRY HAS TO EARN IT. This used to be an
            # unconditional overwrite on the strength of a tag - the
            # one guard here that never looked at what it was
            # keeping. Every test below is already written in this
            # file; they are simply pointed at the retry, at no extra
            # cost, because this is the call that already happened.
            t2, l2 = ask(audio, last)
            secs0 = len(audio) / float(sr)
            worse = (not (t2 or "").strip()          # nothing came back
                     or _foreign(t2)                 # an unread alphabet
                     or _impossible(t2, secs0)       # no mouth is that fast
                     or (ctx and _ctx_echo(t2, ctx)))  # the prompt talking
            # PINNING FORCES THE SCRIPT - the arabizi guard leans on
            # that deliberately - so an answer written in the script
            # the pin was pushing is not evidence about what was
            # said. It is only the PIN that has to be doubted, and
            # only when it pointed away from the first answer:
            # guarding one direction unconditionally made Arabic win
            # every argument and latch there.
            _af1, _af2 = _arabic_frac(txt), _arabic_frac(t2)
            if not worse and ((last == "english"
                               and _af1 >= 0.5 and _af2 < 0.5)
                              or (last == "arabic"
                                  and _af1 < 0.5 and _af2 >= 0.5)):
                worse = True
            if worse and txt and not _foreign(txt) \
                    and not _impossible(txt, secs0):
                stats["leash_kept"] += 1
                lang = None          # the script fix below decides it
                if t2 and t2.strip() != txt.strip():
                    lost = t2.strip()[:300]
            else:
                txt, lang = t2, l2
        if txt and _foreign(txt):
            # a foreign ALPHABET slipped past the language leash: one
            # pinned retry, then the utterance is dropped - silence beats
            # a language nobody in the room speaks
            t2, l2 = ask(audio, last)
            if t2 and not _foreign(t2):
                txt, lang = t2, (l2 or last)
            else:
                txt = ""
        if txt and ctx and _ctx_echo(txt, ctx):
            # THE PROMPT LEAKED. Ask once more with no context at all and
            # trust that answer: words genuinely spoken survive on their
            # own; an echo comes back as nothing (or as what the noise
            # actually was). Never drop the retry - a real sentence that
            # happens to mention the game and Discord is still real.
            # Pin the CURRENT line's accepted language, not the previous
            # line's - pinning stale 'arabic' onto an English line forces
            # Arabic-script output (the Arabizi guard uses that exact
            # trick on purpose). And the retry answers in the
            # hallucination-heaviest regime, so it faces the same
            # alphabet wall every other answer does.
            stats["echo"] += 1
            pin = lang if lang in KEEP else last
            t2, l2 = ask(audio, pin, use_ctx=False)
            if t2 and _foreign(t2):
                t2, l2 = "", None
            txt, lang = (t2 or ""), (l2 or lang)
        if walls and txt and lang != "arabic" \
                and stats["translit"] < TRANSLIT_MAX and _arabizi(txt):
            # ARABIC WRITTEN IN LATIN LETTERS. The guard inside ask()
            # only fires when the model SAYS arabic; this one catches the
            # lines it tagged english, of which "The Nefq?" (the tunnel)
            # became two chapter titles of lore that never happened.
            #
            # Ask once more pinned to Arabic and keep that answer only if
            # it comes back mostly in Arabic script at roughly the same
            # length. THE LENGTH BAND IS THE SAFETY, not the script test:
            # pinning forces Arabic script whatever was said, so the
            # script tells us nothing about whether the answer is right -
            # everything that decides that lives in _arabizi. The band is
            # only here to catch the runaway repetition this whole worker
            # exists to prevent.
            stats["translit"] += 1
            t2, l2 = ask(audio, "arabic")
            if t2 and _arabic_frac(t2) >= 0.5 \
                    and 0.4 <= len(t2) / float(len(txt)) <= 2.5:
                stats["translit_won"] += 1
                txt, lang = t2, (l2 or "arabic")
        if walls and txt and stats["enwall"] < ENWALL_MAX \
                and _arabic_frac(txt) >= 0.5:
            hd = _english_head(txt)
            if hd:
                # ENGLISH WRITTEN IN ARABIC LETTERS - the wall above,
                # the other way round. "قولي الشط الصوت خراب!" is
                # "holy shit" and then real Arabic, and on 2.84 the
                # whole line went to the auditor as Arabic speech.
                #
                # Ask once more pinned to English and keep NOTHING of
                # that answer but a yes or a no: if it says the phrase
                # back, splice OUR phrase over the exact span that
                # sounded it out. Pinning forces Latin letters, so
                # trusting the answer's text would translate his Arabic
                # for him - this way a wrong yes cannot reach one
                # character past the words that were suspect.
                #
                # THE SPLICE KEEPS BOTH SIDES. Rebuilding the line as
                # "phrase + the tail" silently deleted whatever stood
                # in front of the run - a leading "يا" carries no
                # consonant, so the head can start at word two.
                stats["enwall"] += 1
                try:
                    t2, _l2 = ask(audio, "english")
                except Exception as e0:
                    t2 = ""
                    notes.append("the English-in-Arabic wall gave up: "
                                 + str(e0)[:80])
                if t2 and _says(t2, hd[2]):
                    stats["enwall_won"] += 1
                    txt = (txt[:hd[0]] + hd[2][0].upper() + hd[2][1:]
                           + txt[hd[1]:])
                    if _arabic_frac(txt) < 0.5:
                        lang = "english"
        if txt and _impossible(txt, len(audio) / float(sr)):
            # A MOUTH CANNOT SAY THIS. The paraphrase leak lands here:
            # prompt-flavoured sentences stamped on sub-second spans of
            # music, byte-identical across nights because temperature
            # is 0. One retry with the context stripped - words
            # genuinely spoken survive on their own; a fabrication has
            # nothing to come back as. The retry faces this same test,
            # so it cannot smuggle the line back in.
            stats["physics"] += 1
            pin = lang if lang in KEEP else last
            t2, l2 = ask(audio, pin, use_ctx=False)
            if t2 and (_foreign(t2)
                       or _impossible(t2, len(audio) / float(sr))):
                t2, l2 = "", None
            txt, lang = (t2 or ""), (l2 or lang)
        # THE TAG IS THE MODEL'S GUESS; THE SCRIPT IS WHAT IT WROTE.
        # 4,178 Arabic-script lines in this library are tagged
        # "english" - 44% of all Arabic lines - and `last` then learns
        # the lie, so the leash pins English onto an Arabic night and
        # forces Latin output on the re-ask. The characters decide now,
        # BEFORE `last` learns anything.
        if txt:
            _sf_letters = [ch for ch in txt if ch.isalpha()]
            if _sf_letters:
                _sf_ar = sum(1 for ch in _sf_letters
                             if "\u0600" <= ch <= "\u06ff")
                if _sf_ar / float(len(_sf_letters)) > 0.5:
                    lang = "arabic"
                elif sum(1 for ch in _sf_letters
                         if ch.isascii()) / float(len(_sf_letters)) > 0.5:
                    lang = "english"
        slow_n[0] = slow_n[0] + 1 if time.time() - t_ask > 150 else 0
        if slow_n[0] >= 3:
            raise SystemExit(
                "three utterances in a row took over 150s each - the server "
                "is crawling; giving up rather than pinning the job for "
                "hours")
        # A BLANKED LINE TEACHES NOTHING. The walls above blank a
        # condemned line but leave its tag - and the tags of exactly
        # those lines are the least trustworthy in the file. `last`
        # learns only from lines that ship.
        if txt and lang in KEEP:
            last = lang
        return txt, lang, lost

    for i, g in enumerate(groups):
        apply_threads()          # he alt-tabbed; take the machine back (or give it up)
        audio = np.concatenate(g["parts"])
        if len(audio) < sr * 0.4:
            speech_done += g["len"] / float(sr)
            say_progress(i + 1, n_all, speech_done, speech_total)
            continue    # skipped, but the bar must not stall on it
        txt, lang, lost = _read(audio, True, len(audio) / float(sr))
        if txt:
            if lost:
                # the answer that did not win is kept beside the one
                # that did - a leash swap used to leave no trace at
                # all, so nothing could ever be measured after
                sg_new_alt = lost
            else:
                sg_new_alt = None
            sg_new = {"a": int(g["start"] / sr * 1000),
                      "b": int(g["end"] / sr * 1000), "t": txt,
                      "lang": lang or last}
            mfrac = g.get("mic", 0) / float(max(1, g["len"]))
            if mfrac >= 0.9:
                sg_new["src"] = "you"       # read from his clean mic
                stats["mic_lines"] += 1
            elif mfrac > 0:
                # partially mic-sourced: say HOW much, never a binary
                # that would be wrong in both directions
                sg_new["micp"] = round(mfrac, 2)
            if sg_new_alt:
                sg_new["alt"] = sg_new_alt
            out.append(sg_new)
            gidx.append(i)   # out[k] came from groups[gidx[k]]
        speech_done += g["len"] / float(sr)
        # BY SPEECH, not by utterance count: utterances are wildly uneven, so
        # "40 of 300" says much less about the time left than "12 of 96
        # minutes of talking".
        say_progress(i + 1, n_all, speech_done, speech_total)

    # THE SECOND READING (2.85). Some lines can only be judged once the
    # whole night is on the page, because what gives them away is what
    # was said either side - and inside the loop the next utterance has
    # not been read yet. "Zami hehe." is the shape: one word no
    # dictionary knows, wearing a laugh, with Arabic spoken 2.4 seconds
    # later. Re-ask those pinned to Arabic and hold the answer to the
    # same length band the 2.84 wall uses (that band is there to catch
    # runaway repetition, nothing else).
    for k in range(min(len(out), len(gidx))):
        if stats["laugh"] >= LAUGH_MAX:
            break
        sg = out[k]
        was = sg.get("t") or ""
        if not _laughing_alone(was) or not _arabic_company(out, k):
            continue
        stats["laugh"] += 1
        try:
            t2, l2 = ask(np.concatenate(groups[gidx[k]]["parts"]),
                         "arabic")
        except Exception as e3:
            notes.append("the laughter wall gave up: " + str(e3)[:80])
            break
        if t2 and _arabic_frac(t2) >= 0.5 \
                and 0.4 <= len(t2) / float(len(was)) <= 2.5:
            stats["laugh_won"] += 1
            sg["t"], sg["lang"] = t2, (l2 or "arabic")

    # 3.31 THE SECOND AND THIRD PASSES: what a video said, and what the
    # game said, read by the same model through the same fabrication
    # gates but with their OWN context and WITHOUT the house walls, and
    # filed by source so nothing downstream can mistake them for the
    # room. `last` is saved and put back: a video must not teach the
    # leash its language and pin it onto the room.
    _last_room = last
    done_n = len(groups)
    for kind, glist, cctx, why in (("media", groups_media, ctx_media,
                                    smeta["why"]),
                                   ("game", groups_game, ctx_game,
                                    "game tap")):
        if not glist:
            continue
        cur_ctx[0] = cctx
        for g in glist:
            apply_threads()
            audio = np.concatenate(g["parts"])
            done_n += 1
            if len(audio) < sr * 0.4:
                speech_done += g["len"] / float(sr)
                say_progress(done_n, n_all, speech_done, speech_total)
                continue
            txt, lang, _lost = _read(audio, False, len(audio) / float(sr))
            if txt:
                out.append({"a": int(g["start"] / sr * 1000),
                            "b": int(g["end"] / sr * 1000), "t": txt,
                            "lang": lang or last, "src": kind, "why": why})
                stats[kind + "_lines"] += 1
            speech_done += g["len"] / float(sr)
            say_progress(done_n, n_all, speech_done, speech_total)
    cur_ctx[0] = ctx
    last = _last_room
    out.sort(key=lambda s3: s3["a"])

    # THE MIC LAYER (2.81+): the mic track's own speech spans say which
    # lines are HIS voice - a cutscene or a background tab has no mic
    # energy, a spoken line does. TAGGED, NEVER FILTERED, and nothing is
    # ever cut out of the mix on the strength of it: a friend answering
    # while he talks lives in that same mix utterance, and taking his
    # voice out of the audio would take the friend with it.
    #
    # A SECOND ASR PASS over this clean track was written and thrown
    # away. Measured on the only layered recording he has
    # (hearthstone_20260816_153823, 2h12m, 457 utterances): 424 of those
    # utterances are 90%+ his own microphone, so a mic pass re-reads
    # essentially the whole night - about twice the ASR job, hours on a
    # long one - and it would buy almost nothing, because the mix's own
    # voice detector already found every part of his speech but 0.7
    # seconds of it.
    if ma is not None:
        # "of the ROOM's lines" - a video's or the game's are not his
        _n_room = sum(1 for sg in out
                      if sg.get("src") not in ("media", "game"))
        notes.append(str(stats["mic_lines"]) + " of " + str(_n_room)
                     + " line(s) read from the clean mic itself")
    if mic and os.path.isfile(mic) and ma is None:
        try:
            ma, msr = sf.read(mic, dtype="float32")
            if ma.ndim > 1:
                ma = ma.mean(axis=1)
            mspans = get_speech_timestamps(
                torch.from_numpy(np.ascontiguousarray(ma)),
                load_silero_vad(), sampling_rate=msr,
                min_silence_duration_ms=300, speech_pad_ms=120)
            mm = [(s2["start"] / msr, s2["end"] / msr) for s2 in mspans]
            for sg in out:
                if sg.get("src") in ("media", "game"):
                    continue      # never his voice, whatever the mic did
                a2, b2 = (sg["a"] or 0) / 1000.0, (sg["b"] or 0) / 1000.0
                ov = sum(max(0.0, min(b2, y) - max(a2, x)) for x, y in mm)
                if ov >= 0.4 * max(0.3, b2 - a2):
                    sg["src"] = "you"
                    stats["mic_lines"] += 1
            notes.append("the mic layer marked "
                         + str(stats["mic_lines"]) + " of "
                         + str(len(out)) + " line(s) as his own voice")
        except Exception as e2:
            # this used to be a stderr print, i.e. invisible on every run
            # that succeeded - the app reads the notes and journals them
            notes.append("mic layer skipped: " + str(e2)[:90])

    # tmp + replace: a crash mid-dump must never leave torn JSON under the
    # final name for the app to misread as a finished transcript
    with open(dst + ".tmp", "w", encoding="utf-8") as fh:
        # 'sources' BEFORE 'segments': the app's 8 KB head-read and the
        # per-game ledger rely on the small keys sitting ahead of the
        # lines (json.dump keeps insertion order)
        json.dump({"sources": _sources_block(
                       has_voice, has_game,
                       smeta["media_ran"] and not stats["media_off"],
                       voice_s, mic_s, smeta["room_s"], smeta["game_s"],
                       smeta["media_s"], smeta["media_read_s"],
                       smeta["game_read_s"], stats),
                   "segments": out, "model": MODEL, "engine": engine,
                   "reader": READER, "counters": stats, "notes": notes},
                  fh, ensure_ascii=False)
    os.replace(dst + ".tmp", dst)
    say_progress(len(groups), len(groups), speech_total, speech_total)
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: asr_worker.py <mix.wav> <out.json> [mic.wav]\n"
              "  env: LORE_ASR_VOICE / LORE_ASR_GAME (16 kHz mono wavs of "
              "the Voice and Game taps), LORE_ASR_CONTEXT_MEDIA / "
              "LORE_ASR_CONTEXT_GAME, LORE_ASR_MEDIA=0 (no media "
              "detection), LORE_ASR_GAME_LINES=0 (count game speech, do "
              "not read it)", file=sys.stderr)
        sys.exit(2)
    try:
        sys.exit(main(sys.argv[1], sys.argv[2],
                      sys.argv[3] if len(sys.argv) > 3 else None))
    except Exception as e:
        print(f"ASR_WORKER_FAILED {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
