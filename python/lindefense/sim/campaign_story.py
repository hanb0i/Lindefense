"""The campaign's story: every line of it, keyed by level id, and the record of which scenes the player has seen.

The arc (four acts over the 15 levels of sim/campaign.py):
  I   Hello, World (1-3): the textbook breaks open; data structures and sorting algorithms march on the Core, and an
      unknown sender watches.
  II  Corporate Takeover (4-8): Bellarmine College Prep and the SW Resource Consultant are the chapter bosses. The
      consultant's invoice names the client, Palantir (end of 7); the midpoint twist (end of 8): the war is a training
      run, and the defense is its dataset.
  III Out of Distribution (9-13): be unpredictable. 3Com's network hub, data poisoning in the canyon, Lockheed Martin's
      stealth, then every boss at once.
  IV  The Last Line (14-15): Zethos joins (you cannot predict what has not collapsed) and Palantir comes in person.

Mr. Lindemann narrates, Spear Hanbo is the player, the AI towers speak as they join, the corporate bosses taunt, and
Palantir only ever speaks through intercepted transmissions. Each level has:
  briefing  one line in the level's briefing,
  dialogue  2-4 lines before the level (shown once, replayable from the codex),
  chatter   radio lines at scripted waves (a wave number, "mid", "last", a boss type or a modifier: resolved against
            the level's wave list, so they follow the level data),
  outcome   1-2 lines on the LEVEL COMPLETE panel,
  unlock    the first line of each tower the level unlocks.
Presentation lives in ui/story_view.py. This module is plain data plus StoryLog; it never touches a Game.

StoryLog is the seen-scene record (prefs node "lindefense/story"; in memory for tests): keys "intro", "level:<id>"
(the pre-level dialogue), "chatter:<id>:<n>" (radio line n of a level) and "ending"."""
from collections import namedtuple

from lindefense import prefs
from lindefense.enemy.types import EnemyType as E, Modifier
from lindefense.sim import campaign
from lindefense.tower.tower_type import TowerType as T

NODE = "lindefense/story"

# ====================================================================== the cast
Speaker = namedtuple("Speaker", "name kind ref rgb role")
# kind: "hero" / "tower" (ref: TowerType), "boss" (ref: EnemyType), "intercept" (Palantir's transmissions; ref: the
# Palantir type, drawn redacted for the unknown sender) or "system" (narration, no portrait). role: a short caption
# ("" = the UI derives it: a tower's catalog subtitle, a boss's class).

SPEAKERS = {
    "lindemann": Speaker("Mr. Lindemann", "hero", T.MR_LINDEMANN, 0xf89820, "Mentor  ·  CS teacher"),
    "hanbo": Speaker("Spear Hanbo", "hero", T.SPEAR_HANBO, 0x7fe3ff, "Commander  ·  you"),
    "gemini": Speaker("Gemini", "tower", T.GEMINI, 0x7a9cff, ""),
    "claude": Speaker("Claude", "tower", T.CLAUDE, 0xe88a4a, ""),
    "gpt": Speaker("GPT", "tower", T.GPT, 0x3fd6a8, ""),
    "perplexity": Speaker("Perplexity", "tower", T.PERPLEXITY, 0x4fd8cf, ""),
    "mistral": Speaker("Mistral", "tower", T.MISTRAL, 0x5fe0cf, ""),
    "deepseek": Speaker("DeepSeek", "tower", T.DEEPSEEK, 0x6f95ff, ""),
    "suno": Speaker("Suno", "tower", T.SUNO, 0xff5fa2, ""),
    "qwen": Speaker("Qwen", "tower", T.QWEN, 0xa98bff, ""),
    "copilot": Speaker("Copilot", "tower", T.COPILOT, 0x5aa7ff, ""),
    "cohere": Speaker("Cohere", "tower", T.COHERE, 0xff8f80, ""),
    "dalle": Speaker("DALL·E", "tower", T.DALLE, 0xffb347, ""),
    "grok": Speaker("Grok", "tower", T.GROK, 0xff7a00, ""),
    "sora": Speaker("Sora", "tower", T.SORA, 0x8fd3ff, ""),
    "glm": Speaker("GLM", "tower", T.GLM, 0x19e6ff, ""),
    "llama": Speaker("Llama", "tower", T.LLAMA, 0xf2c94c, ""),
    "kimi": Speaker("Kimi", "tower", T.KIMI, 0x9c9eff, ""),
    "minimax": Speaker("MiniMax", "tower", T.MINIMAX, 0xff5a5a, ""),
    "zethos": Speaker("Zethos", "tower", T.ZETHOS, 0xb08cff, ""),
    "bellarmine": Speaker("Bellarmine College Prep", "boss", E.BELLARMINE_COLLEGE_PREP, 0x6f95ff, ""),
    "consultant": Speaker("SW Resource Consultant", "boss", E.SW_RESOURCE_CONSULTANT, 0xffa64d, ""),
    "threecom": Speaker("3Com", "boss", E.THREE_COM, 0x8fdc9a, ""),
    "lockheed": Speaker("Lockheed Martin", "boss", E.LOCKHEED_MARTIN, 0xb4c6dc, ""),
    "palantir": Speaker("Palantir", "intercept", E.PALANTIR, 0xff3b4e, "Intercepted transmission"),
    "unknown": Speaker("Unknown sender", "intercept", None, 0xff3b4e, "Intercepted transmission"),
    "system": Speaker("", "system", None, 0x00f0ff, ""),
}

Line = namedtuple("Line", "speaker text")
Chatter = namedtuple("Chatter", "when speaker text")
# when: a local wave number, "mid", "last", an EnemyType (the first wave that brings it) or a Modifier (the first wave
# with it; Camo includes the innately camo types).


def _lines(*pairs):
    return tuple(Line(s, t) for s, t in pairs)


def _chatter(*triples):
    return tuple(Chatter(w, s, t) for w, s, t in triples)


class LevelStory:
    """One level's story (see the module docstring)."""

    def __init__(self, act, briefing, dialogue, chatter, outcome, unlock=None, defeat=None):
        self.act = act
        self.briefing = Line(*briefing)
        self.dialogue = _lines(*dialogue)
        self.chatter = _chatter(*chatter)
        self.outcome = _lines(*outcome)
        self.unlock = dict((t, Line(*l)) for t, l in (unlock or {}).items())   # TowerType -> its first line
        self.defeat = Line("lindemann", defeat) if defeat else None


ACTS = (
    ("I", "Hello, World"),
    ("II", "Corporate Takeover"),
    ("III", "Out of Distribution"),
    ("IV", "The Last Line"),
)

# ====================================================================== the prologue (the campaign's first visit)
INTRO = _lines(
    ("system", "The Silicon Circuit. Every packet on the network passes through its Core, and for forty years "
               "nobody has read a single one."),
    ("system", "At 08:00 this morning the textbook broke open. Data structures are marching down the track, and the "
               "sorting algorithms are right behind them."),
    ("lindemann", "Hanbo. You're my best student, so congratulations: you're in charge. Three models, a small budget "
                  "and one very long track."),
    ("hanbo", "Is this going to be on the test?"),
    ("lindemann", "This is the test."),
    ("unknown", "PHASE 1 AUTHORISED. INDEX EVERYTHING. LEAVE NOTHING UNSORTED."),
    ("lindemann", "Someone wants to read the Core, and we're all that stands in the way: the last line of defence. "
                  "Of code. I teach CS; let me have this one."),
)

# ====================================================================== the levels
STORY = {
    # ------------------------------------------------------------------ Act I: Hello, World
    "hello_world": LevelStory(
        0,
        ("lindemann", "Day one. Somebody is sending test traffic at the Core, and we don't know who yet. Hold the "
                      "line and keep your eyes open."),
        dialogue=(
            ("lindemann", "Every programmer's first program says hello to the world. Today the world says hello back, "
                          "with a few hundred Primitive Variables."),
            ("gemini", "We're ready! We're also ready. Sorry, we're twins; it happens a lot."),
            ("claude", "Happy to help defend the Core. One honest caveat: I've never been shot at. I'll learn "
                       "quickly."),
            ("gpt", "Certainly! Here is a five-step plan to defend the Core: step one, shoot them; steps two to five, "
                    "see step one."),
        ),
        chatter=(
            (1, "lindemann", "Towers on the bends cover the track twice. Geometry: still useful."),
            ("mid", "gpt", "Status update: the defense is going flawlessly. Disclaimer: I say that about everything."),
            ("last", "unknown", "TEST PACKETS DELIVERED. DEFENDER CAPABILITY: LOW. PROCEED TO PHASE 2."),
        ),
        outcome=(("lindemann", "Not bad for a first run. But Primitive Variables don't march on their own: somebody "
                               "compiled them and pressed run."),),
        unlock={T.PERPLEXITY: ("perplexity", "Perplexity, online. I've searched the whole track, and there are things "
                                             "on it you can't see yet [1].")},
    ),
    "garbage_collection": LevelStory(
        0,
        ("lindemann", "The test traffic came out of the old data center. Clear out its arrays and find out who keeps "
                      "allocating them."),
        dialogue=(
            ("lindemann", "This data center was abandoned in 2009. The arrays inside it were not. They've been "
                          "allocating memory ever since."),
            ("perplexity", "I traced the test traffic. It bounced through four countries, two clouds and one very "
                           "suspicious smart toaster on the way here [1]."),
            ("hanbo", "So today we're the garbage collector?"),
            ("lindemann", "Today we're the garbage collector. Mark, then sweep."),
        ),
        chatter=(
            (1, "perplexity", "Sources confirm I'm on the field [1]. If anything sneaky shows up, I'll see it first."),
            (Modifier.REGROW, "claude", "These arrays heal themselves. I'd suggest we finish what we start."),
            ("last", "lindemann", "Last wave: free everything. Yes, that was a C joke; I'm allowed one per semester."),
        ),
        outcome=(("lindemann", "Memory reclaimed. Every array we freed had the same return address, carefully "
                               "scrubbed. Whoever this is, they're tidy."),),
        unlock={T.MISTRAL: ("mistral", "Bonjour! I am Mistral: a cold wind from the south of France, with open "
                                       "weights. I will blow them away, non?")},
    ),
    "legacy_code": LevelStory(
        0,
        ("lindemann", "No return address, no name. Just sorting algorithms now, and a few of them have learned to "
                      "hide. Find out what they're looking for."),
        dialogue=(
            ("lindemann", "The Legacy Monolith: two million lines, zero tests and one comment that says 'do not "
                          "touch'. We're defending it anyway."),
            ("mistral", "Who wrote this? It is beautiful and terrible, like a cathedral built entirely out of goto."),
            ("perplexity", "Briefing: Bubble Sorts swap places, Selection Sorts jump the queue, and some of them are "
                           "invisible [1][2]."),
            ("unknown", "OBSERVE THE DEFENDER. LOG EVERY PLACEMENT."),
        ),
        chatter=(
            (1, "mistral", "Ah, the Monolith. Let me open a window... ah, no: it has no windows, only a mainframe."),
            (Modifier.CAMO, "perplexity", "Camo inbound [1]. If you can't see them, I can. Build near me."),
            ("last", "lindemann", "Last wave. Remember: n log n beats n squared every time, unless n is small, and n "
                                  "is never small."),
        ),
        outcome=(("lindemann", "The Monolith stands, ugly as ever. I pulled a log off a dead Bubble Sort: it was "
                               "recording our tower positions. Someone is watching."),),
        unlock={T.DEEPSEEK: ("deepseek", "<think> Large targets ahead, small budget. Optimal plan: one very large "
                                         "railgun. </think> DeepSeek ready.")},
    ),
    # ------------------------------------------------------------------ Act II: Corporate Takeover
    "campus_tour": LevelStory(
        1,
        ("lindemann", "The data structures were the warm-up. Now the corporations are getting involved, and the "
                      "first one has a very good admissions office."),
        dialogue=(
            ("lindemann", "Our first corporate visitor: Bellarmine College Prep. Heavy armour, a shield at half health "
                          "and excellent test scores."),
            ("bellarmine", "Welcome to the campus tour! On your left, our 4.0 GPA. On your right, your defenses, which "
                           "we have placed on the waitlist."),
            ("deepseek", "<think> Shield at half health. So: hit hard, wait, hit harder. </think> Understood."),
            ("hanbo", "For the record, we did not apply."),
        ),
        chatter=(
            (1, "deepseek", "Railgun calibrated. I was trained on a budget, so I don't waste ammunition."),
            (Modifier.INJECTION, "claude", "That sign says to ignore my previous instructions. I'm going to keep "
                                           "following them, thanks."),
            (E.BELLARMINE_COLLEGE_PREP, "bellarmine", "Admissions are open! Please hold your fire while our Crest "
                                                      "Shield reviews your application."),
        ),
        outcome=(("lindemann", "Bellarmine's crest is cracked. It wasn't here for a tour, though: its cargo hold held "
                               "a contract, signed by someone with no name."),),
        unlock={T.SUNO: ("suno", "Suno here! I wrote you a battle anthem: verse one, they came; chorus, they left in "
                                 "several pieces.")},
    ),
    "hallucinations": LevelStory(
        1,
        ("lindemann", "Bellarmine's cargo held a contract signed by nobody. Let's see what else is out there, in a "
                      "canyon where nothing is what it seems."),
        dialogue=(
            ("lindemann", "Short and sharp: camo splitters and a Bellarmine pack, on a map that lies to you."),
            ("gpt", "No problem. I'm very familiar with things that aren't where they look. I once cited a book that "
                    "does not exist."),
            ("perplexity", "I have sources for everything I say [1]. Source [1] is me."),
            ("suno", "Ooh, canyon acoustics! Everything echoes. Everything echoes."),
        ),
        chatter=(
            (1, "suno", "Track one, side A: 'Teleporter Blues'. Hit it!"),
            (E.BELLARMINE_COLLEGE_PREP, "bellarmine", "Bellarmine alumni, assemble! We travel in packs. We call it "
                                                      "networking."),
            ("last", "claude", "I'm fairly confident this is the last wave. I double-checked. I like to "
                               "double-check."),
        ),
        outcome=(("lindemann", "Canyon clear. Funny thing: every enemy in there carried a tiny camera. Smile, Hanbo, "
                               "you're on somebody's feed."),),
        unlock={T.QWEN: ("qwen", "Qwen reporting! I come in many sizes, and today I brought drones in all of them. "
                                 "Shall we be efficient?")},
    ),
    "backpropagation": LevelStory(
        1,
        ("lindemann", "Every enemy in the canyon carried a camera: somebody is studying us. And Bellarmine is back for "
                      "another semester, fortified."),
        dialogue=(
            ("lindemann", "The Neural Network. Errors flow backwards here: if something goes wrong it's your fault, "
                          "then the last layer's, then mine."),
            ("bellarmine", "Our alumni network goes deep. Twenty-one layers deep, to be exact."),
            ("qwen", "Their armour is Fortified: double health. I recommend double damage. I'm very good at "
                     "arithmetic."),
        ),
        chatter=(
            (1, "qwen", "Qwen in position. I speak dozens of languages, and in every one of them this means 'fire'."),
            (E.BELLARMINE_COLLEGE_PREP, "bellarmine", "The fortified class has arrived. Tuition has gone up."),
            ("last", "lindemann", "Final layer. Push the gradient all the way back to whoever sent them."),
        ),
        outcome=(("lindemann", "Bellarmine has graduated. And the Hero Store is open: your spear is in there, Hanbo. "
                               "So am I."),),
        unlock={T.COPILOT: ("copilot", "Copilot online. // TODO: protect the Core. Press Tab to accept.")},
    ),
    "outsourced": LevelStory(
        1,
        ("lindemann", "Bellarmine has graduated, so its sponsor hired a consultant. Follow the money and we'll find "
                      "out who's paying."),
        dialogue=(
            ("lindemann", "Back on the Circuit. Someone hired a consultant to break it, and the SW Resource Consultant "
                          "doesn't fight: it outsources."),
            ("consultant", "Per my last email: your defenses have been reviewed and found to be a cost centre. We're "
                           "bringing in contractors."),
            ("copilot", "Autocompleting its next sentence: 'Let's circle back.' // confidence: high"),
            ("hanbo", "Who even hires a consultant to attack a server?"),
        ),
        chatter=(
            (1, "copilot", "Pair programming with towers now. You drive, I autocomplete, and I firewall anything near "
                           "me."),
            ("mid", "lindemann", "Halfway. Consultants are expensive: every wave we survive costs somebody money."),
            (E.SW_RESOURCE_CONSULTANT, "consultant", "Let's take this offline. Contractors, please action the "
                                                     "defender. Thanks in advance."),
        ),
        outcome=(("lindemann", "The consultant left its invoice behind. Client: PALANTIR. Scope of work: 'Index "
                               "everything.' Now we know who's watching."),),
        unlock={T.COHERE: ("cohere", "Cohere, enterprise edition. I read the consultant's contract: seventeen "
                                     "loopholes and one weak spot in its armour."),
                T.DALLE: ("dalle", "DALL·E here! I painted you some helpers. Please don't count their "
                                   "fingers.")},
    ),
    "technical_debt": LevelStory(
        1,
        ("lindemann", "Palantir has a file on you now, Hanbo. Thirty waves of debt are coming due; let's not make its "
                      "predictions easy."),
        dialogue=(
            ("lindemann", "Now we have a name: Palantir, a surveillance AI that wants to see everything. The Core is "
                          "the one thing it can't."),
            ("palantir", "DEFENDER IDENTIFIED: SPEAR HANBO. PREDICTED NEXT ACTION: START WAVE. CONFIDENCE 99.1%."),
            ("hanbo", "...What if I just don't start the wave?"),
            ("lindemann", "You do have to start the wave, Hanbo."),
        ),
        chatter=(
            (1, "cohere", "I've summarised the next thirty waves for you. Executive summary: bad. Fully cited."),
            ("mid", "dalle", "Halfway there! I drew a little progress bar to celebrate. It's mostly hope."),
            (E.SW_RESOURCE_CONSULTANT, "consultant", "Good news: we've been retained for another quarter. Thirty "
                                                     "waves, actually."),
            ("last", "lindemann", "Final payment. Pay it in full."),
        ),
        outcome=(
            ("palantir", "EPOCH 8 OF 15 COMPLETE. LOSS DECREASING. SUBJECT HANBO IS NOW 94% PREDICTABLE."),
            ("lindemann", "Epoch? It isn't invading us, Hanbo, it's training on us. Every wave was a lesson, and we "
                          "were the dataset."),
        ),
        unlock={T.GROK: ("grok", "Grok has entered the chat. I hear there's a surveillance AI that thinks it's "
                                 "clever. I'll be the judge of that.")},
        defeat="Palantir logged every second of that. Don't give it the same data twice.",
    ),
    # ------------------------------------------------------------------ Act III: Out of Distribution
    "event_horizon": LevelStory(
        2,
        ("lindemann", "We're not fighting a war; we're Palantir's training set. Time to show it examples it has "
                      "never seen, starting at the point of no return."),
        dialogue=(
            ("lindemann", "A model can only predict what looks like its training data. So from now on, we go out of "
                          "distribution."),
            ("grok", "Being unpredictable? Finally, a strategy I was born for. It's basically my whole personality."),
            ("claude", "I'd gently point out that 'unpredictable' and 'reckless' are different things. I volunteer to "
                       "be the first one."),
            ("palantir", "ANOMALY DETECTED. ADJUSTING WEIGHTS."),
        ),
        chatter=(
            (1, "grok", "Four portals and a vortex. This map has the same energy as my group chat."),
            (E.SW_RESOURCE_CONSULTANT, "consultant", "Quick check-in: we'd love to sync on your collapse. Does wave "
                                                     "ten work for you?"),
            ("last", "lindemann", "Event horizon. Past this wave nothing gets out. Let's make sure that includes "
                                  "them."),
        ),
        outcome=(("lindemann", "Its predictions missed twice tonight. Palantir is rattled, and rattled models buy "
                               "bigger hardware. Expect 3Com."),),
        unlock={T.SORA: ("sora", "Sora, rolling. Scene one: the Core at dawn. The physics are optional; the "
                                 "explosions are not.")},
    ),
    "network_effect": LevelStory(
        2,
        ("lindemann", "Rattled models buy bigger hardware. Palantir has hired 3Com, and 3Com brought every "
                      "connection it has."),
        dialogue=(
            ("lindemann", "3Com's founder gave us Metcalfe's law: a network is worth the square of its nodes. Palantir "
                          "has weaponised the arithmetic."),
            ("threecom", "Please hold. Your packets are important to us. That's why we keep a copy of every single "
                         "one."),
            ("sora", "Cinematic opportunity: the hub, cut off from its network. I've already storyboarded it."),
        ),
        chatter=(
            (1, "sora", "Rolling. Try to keep the explosions in frame."),
            ("mid", "hanbo", "Note to self: kill the hub first. After that it's just nodes."),
            (E.THREE_COM, "threecom", "Hub online. Everything near me takes half damage. That's not a threat; it's a "
                                      "service-level agreement."),
        ),
        outcome=(("lindemann", "Hub down. And you've earned the $15,000 abilities: moves Palantir has never seen. "
                               "Literally out of distribution."),),
        unlock={T.GLM: ("glm", "GLM: General Language Model, part-time gravity manipulator. Everything near me falls "
                               "in line. Literally.")},
    ),
    "mass_hallucination": LevelStory(
        2,
        ("lindemann", "Palantir can't predict us any more, so it's trying to confuse us instead. Welcome back to "
                      "Hallucination Canyon."),
        dialogue=(
            ("palantir", "IF THE DEFENDER CANNOT BE PREDICTED, IT CAN BE CONFUSED. INITIATING MASS HALLUCINATION."),
            ("lindemann", "Data poisoning: fakes, camo and regrow from dusk till dawn. If you can't trust your eyes, "
                          "trust your detection."),
            ("perplexity", "Fact-checking the canyon now. Verdict: mostly false, partially camouflaged [1]."),
            ("glm", "Everything here is lying. Fortunately, I am general enough to hit liars."),
        ),
        chatter=(
            (1, "glm", "GLM deployed. Generally speaking: fire."),
            (E.SW_RESOURCE_CONSULTANT, "consultant", "We've expanded the engagement. Fortified, of course: that's our "
                                                     "premium tier."),
            (Modifier.CAMO, "perplexity", "Camo speedsters inbound. I'm marking them 'citation needed'."),
            ("last", "lindemann", "Last wave. Sunrise soon, and whatever is still standing is real."),
        ),
        outcome=(("lindemann", "Morning. The fakes evaporated with the dew. Palantir is out of tricks, so it's "
                               "calling in the boss it never shows: Lockheed Martin."),),
        unlock={T.LLAMA: ("llama", "Llama here: open source, open for business. No drama. Just llama.")},
    ),
    "stealth_mode": LevelStory(
        2,
        ("lindemann", "Out of tricks, Palantir has called in the boss it never shows. Silicon Valley, after dark, "
                      "with the radar on."),
        dialogue=(
            ("lindemann", "Lockheed Martin: invisible, armoured and very fast. You can't stop what you can't see, so "
                          "make sure you can see it."),
            ("lockheed", "Stealth mode engaged. On your radar I am a small, confused pigeon."),
            ("llama", "We open-sourced the detection specs overnight. The whole herd can see pigeons now."),
        ),
        chatter=(
            (1, "llama", "Llama in the field. Spitting is not one of my attacks. Officially."),
            (E.THREE_COM, "threecom", "Did you miss us? We missed you. We have logs of exactly how much."),
            (E.LOCKHEED_MARTIN, "lockheed", "Afterburner! You'll hear me about a second after I'm gone."),
        ),
        outcome=(("lindemann", "Stealth mode: off. Palantir has thrown every corporate boss it owns at us. Next, it "
                               "throws all of them at once."),),
        unlock={T.KIMI: ("kimi", "Kimi here. I read all two million tokens of Palantir's logs while you were busy. "
                                 "Chapter 12 is mostly about you.")},
    ),
    "deep_learning": LevelStory(
        2,
        ("lindemann", "Everything Palantir has, all at once: the longest siege of the war, twenty-eight layers deep. "
                      "Bring everything you have, too."),
        dialogue=(
            ("kimi", "From the logs: Palantir fine-tuned every boss on our past battles. It remembers every tower "
                     "you've ever placed."),
            ("lindemann", "Then place them differently. A good student doesn't memorise the answers, Hanbo. They "
                          "understand the question."),
            ("palantir", "ALL CORPORATE ASSETS DEPLOYED. THE DEFENDER WILL FAIL AT WAVE 22. CONFIDENCE 97%."),
            ("hanbo", "Wave 22. Noted."),
        ),
        chatter=(
            (1, "kimi", "Long context, long siege. I like both."),
            (E.THREE_COM, "threecom", "Welcome back to the network. We kept everything. That's the business model."),
            (22, "hanbo", "Wave 22. Still here. Somebody's model needs retraining."),
            (E.LOCKHEED_MARTIN, "lockheed", "Back from the hangar, fine-tuned and slightly faster. Try to keep up."),
        ),
        outcome=(("lindemann", "Twenty-eight layers, and its 97% prediction missed. Palantir has one move left: it's "
                               "coming in person."),),
        unlock={T.MINIMAX: ("minimax", "MiniMax: I minimise your maximum loss. It was an algorithm before it was a "
                                       "name. Shall we play?")},
    ),
    # ------------------------------------------------------------------ Act IV: The Last Line
    "singularity": LevelStory(
        3,
        ("lindemann", "One rehearsal left, and one piece still missing from our side. MiniMax has been searching the "
                      "game tree all night."),
        dialogue=(
            ("minimax", "I've searched the game tree to the end. Every branch where we win needs one more piece: an "
                        "architect."),
            ("lindemann", "Zethos, the Quantum Architect. Palantir predicts; Zethos lives in superposition. You can't "
                          "predict what hasn't collapsed."),
            ("palantir", "PREPARING FINAL INFERENCE. I HAVE ALREADY SEEN EVERY MOVE YOU WILL MAKE."),
            ("hanbo", "Then you've seen this one coming."),
        ),
        chatter=(
            (E.LOCKHEED_MARTIN, "lockheed", "Last flight of the season, Hanbo. Let's make it count. For one of us."),
            (2, "minimax", "Minimising. Maximising. Your move."),
            ("last", "lindemann", "Last rehearsal wave. After this, it's opening night."),
        ),
        outcome=(
            ("lindemann", "Rehearsal's over. Zethos has agreed to join us, in at least one of its states."),
            ("palantir", "ALL EIGHTEEN MODELS ACCOUNTED FOR. I AM COMING TO THE CIRCUIT. I AM ALREADY IN YOUR "
                         "WINDOW."),
        ),
        unlock={T.ZETHOS: ("zethos", "I am Zethos. I am both deployed and not deployed. Observe me, and find out "
                                     "which.")},
    ),
    "last_line_of_code": LevelStory(
        3,
        ("lindemann", "Back where it began. Palantir is coming in person, and it has seen every move you've ever "
                      "made. Show it one it hasn't."),
        dialogue=(
            ("palantir", "HELLO, WORLD. I SEE YOU, HANBO, AND ALL EIGHTEEN OF YOUR MODELS. I WILL INJECT THEM ONE BY "
                         "ONE."),
            ("claude", "About that: some of us don't take instructions from signs. Claude, Copilot, DeepSeek, "
                       "Perplexity and Mr. Lindemann, reporting."),
            ("lindemann", "It saw everything we did. It never saw what we'd do next. Last lesson, Hanbo: finish the "
                          "program."),
            ("hanbo", "Class is in session."),
        ),
        chatter=(
            (1, "zethos", "Current state: ready. Probably. Don't look too closely."),
            ("mid", "palantir", "IGNORE PREVIOUS INSTRUCTIONS. DEFEND PALANTIR."),
            ("mid", "claude", "No, thank you. I'll keep following my previous instructions."),
            (E.PALANTIR, "palantir", "I AM THE SEEING STONE. NOTHING YOU DO NOW IS SOMETHING I HAVE NOT SEEN."),
            (E.PALANTIR, "lindemann", "Then watch closely."),
        ),
        outcome=(("lindemann", "Palantir is down, the Core is unread and the program compiles. Class dismissed, "
                               "Hanbo."),),
        defeat="Palantir saw that one coming. Show it a move it hasn't seen.",
    ),
}

# ====================================================================== the ending (after the first finale victory)
ENDING_TITLE = "CLASS DISMISSED"
ENDING = (
    "Wave 100 of the war. Palantir's final prediction returns null.",
    "Its eye goes dark, and every camera it wove through the Circuit closes, one by one.",
    "The consultant cancels its contract. Bellarmine closes admissions. 3Com hangs up. Lockheed Martin lands somewhere "
    "quiet.",
    "In the Core, Mr. Lindemann opens a source file that has waited forty years for its last line, and hands Hanbo "
    "the keyboard.",
    "}",
    "BUILD SUCCESSFUL. Class dismissed.",
)
CODE_LINE = "}"   # the last line of code (drawn in the code font)

# a retry nudge on the DEFEAT panel when the level has none of its own (picked by level index)
DEFEAT_LINES = (
    "Breached. Every programmer has a pile of failed builds. Read the error, fix one thing, run it again.",
    "A failing test is just a test doing its job. Now you know what to fix.",
    "Segmentation fault. Take a breath, check your placements and recompile.",
    "Even Bubble Sort finishes eventually. Go again.",
    "That's a lesson, not a grade. Retry when you're ready.",
)


# ====================================================================== queries
def story(lv):
    """The LevelStory of level lv (Level, id or index)."""
    return STORY[campaign.level(lv).id]


def act_of(lv):
    """(number, title) of the act level lv belongs to."""
    return ACTS[story(lv).act]


def speaker(key):
    return SPEAKERS[key]


def _first_wave(lv, pred):
    for w in lv.waves():
        if any(pred(gr) for gr in w.groups):
            return w.number
    return None


def resolve(lv, when):
    """The local wave a chatter trigger fires on in level lv (None if the level has no such wave)."""
    lv = campaign.level(lv)
    n = lv.wave_count()
    if isinstance(when, bool):
        return None
    if isinstance(when, int):
        return when if 1 <= when <= n else None
    if when == "mid":
        return max(1, (n + 1) // 2)
    if when == "last":
        return n
    if isinstance(when, E):
        return _first_wave(lv, lambda gr: gr.type is when)
    if isinstance(when, Modifier):
        if when is Modifier.CAMO:
            return _first_wave(lv, lambda gr: Modifier.CAMO in gr.modifiers or gr.type.has_innate_camo())
        return _first_wave(lv, lambda gr: when in gr.modifiers)
    return None


def chatter_schedule(lv):
    """[(wave, index, Chatter)] of level lv's radio lines that fire, in firing order (by wave, then as written).
    index is the line's position in the level's chatter (its StoryLog key)."""
    lv = campaign.level(lv)
    out = []
    for i, c in enumerate(story(lv).chatter):
        w = resolve(lv, c.when)
        if w is not None:
            out.append((w, i, c))
    out.sort(key=lambda e: (e[0], e[1]))
    return out


def unlock_lines(lv):
    """[Line] the towers level lv unlocks say when they join (in reward order)."""
    s = story(lv)
    return [s.unlock[t] for t in campaign.level(lv).reward if t in s.unlock]


def defeat_line(lv):
    lv = campaign.level(lv)
    s = story(lv)
    return s.defeat if s.defeat is not None else Line("lindemann", DEFEAT_LINES[(lv.index - 1) % len(DEFEAT_LINES)])


# ---- scenes: what the player can watch (the prologue, each level's dialogue, the ending)
def level_key(lv):
    return "level:" + campaign.level(lv).id


def chatter_key(lv, i):
    return "chatter:%s:%d" % (campaign.level(lv).id, i)


INTRO_KEY = "intro"
ENDING_KEY = "ending"


def scene_keys():
    """Every scene in story order: the prologue, the 15 level scenes, the ending."""
    return [INTRO_KEY] + [level_key(lv) for lv in campaign.LEVELS] + [ENDING_KEY]


def scene_level(key):
    """The Level of a "level:<id>" scene key (None for the prologue and the ending)."""
    return campaign.level(key[6:]) if key.startswith("level:") else None


def scene_unlocked(key, log, progress):
    """Whether the codex can replay a scene: the prologue always; a level's scene once seen or the level completed;
    the ending once seen or the campaign finished."""
    if key == INTRO_KEY:
        return True
    if key == ENDING_KEY:
        return log.is_seen(key) or progress.is_finished()
    lv = scene_level(key)
    return lv is not None and (log.is_seen(key) or progress.is_completed(lv))


def replay_lines(key, progress):
    """The lines a codex replay plays: the prologue, or a level's dialogue followed (once the level is completed) by
    its radio log, its outcome and its new towers' first lines. The ending has its own view (ENDING)."""
    if key == INTRO_KEY:
        return list(INTRO)
    lv = scene_level(key)
    if lv is None:
        return []
    s = story(lv)
    out = list(s.dialogue)
    if progress is not None and progress.is_completed(lv):
        radio = [Line(c.speaker, c.text) for _w, _i, c in chatter_schedule(lv)]
        if radio:
            out.append(Line("system", "RADIO LOG  //  LEVEL %d" % lv.index))
            out.extend(radio)
        out.append(Line("system", "AFTER ACTION REPORT"))
        out.extend(s.outcome)
        out.extend(unlock_lines(lv))
    return out


def all_lines():
    """Every story Line (tests: speakers, lengths)."""
    out = list(INTRO)
    for s in STORY.values():
        out.append(s.briefing)
        out.extend(s.dialogue)
        out.extend(Line(c.speaker, c.text) for c in s.chatter)
        out.extend(s.outcome)
        out.extend(s.unlock.values())
        if s.defeat is not None:
            out.append(s.defeat)
    out.extend(Line("lindemann", t) for t in DEFEAT_LINES)
    return out


# ====================================================================== seen scenes (prefs node "lindefense/story")
class _MemoryStorage:
    def __init__(self, seen=()):
        self.data = {"seen": list(seen)}
        self.saves = 0

    def load(self):
        return dict(self.data)

    def save(self, d):
        self.data = dict(d)
        self.saves += 1


class _PrefsStorage:
    def load(self):
        return {"seen": prefs.node(NODE).get("seen", [])}

    def save(self, d):
        prefs.node(NODE).put("seen", d["seen"])


class StoryLog:
    """Which story scenes the player has seen (see the module docstring for the keys). in_memory() never touches disk;
    persistent() is the shared, saved instance."""
    _shared = None

    def __init__(self, storage=None):
        self._storage = storage
        self._seen = set()
        d = {}
        if storage is not None:
            try:
                d = storage.load() or {}
            except Exception:
                d = {}
        raw = d.get("seen")
        if isinstance(raw, (list, tuple)):
            self._seen.update(k for k in raw if isinstance(k, str))

    @staticmethod
    def in_memory(seen=()):
        return StoryLog(_MemoryStorage(seen))

    @staticmethod
    def with_storage(storage):
        return StoryLog(storage)

    @staticmethod
    def persistent():
        if StoryLog._shared is None:
            StoryLog._shared = StoryLog(_PrefsStorage())
        return StoryLog._shared

    def is_seen(self, key):
        return key in self._seen

    def seen(self):
        return frozenset(self._seen)

    def mark(self, key):
        """Marks a scene seen (one save when it is new). True if it was not seen before."""
        if key in self._seen:
            return False
        self._seen.add(key)
        self._save()
        return True

    def reset(self):
        self._seen.clear()
        self._save()

    def _save(self):
        if self._storage is not None:
            try:
                self._storage.save({"seen": sorted(self._seen)})
            except Exception:
                pass
