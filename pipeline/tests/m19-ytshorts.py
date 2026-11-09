#!/usr/bin/env python
"""m19-ytshorts.py: fixtures and a self-test for the youtube-shorts exporter (M19).

  python pipeline/tests/m19-ytshorts.py fixtures DIR
      writes DIR/single1.json single2.json single3.json serial-part1.json serial-mid.json serial-final.json (input.json
      files of runs/<run>/export/, input.schema.json of pipeline/platforms/youtube-shorts) and, next to each,
      answer-ok-<name>.json (a model answer that passes every check)
  python pipeline/tests/m19-ytshorts.py selftest
      runs the exporter in-process on those fixtures and on planted faults; prints PASS/FAIL lines and
      "RESULT: n passed, m failed"; exit 1 when any failed. Touches only a temp folder.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EXPORTER_PATH = os.path.join(REPO, "pipeline", "platforms", "youtube-shorts", "exporter.py")
EM_DASH = chr(0x2014)
NAMES = ["single1", "single2", "single3", "serial-part1", "serial-mid", "serial-final"]


def setup_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            pass


def load_exporter():
    spec = importlib.util.spec_from_file_location("ytshorts_exporter", EXPORTER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------------ fixtures

def desc(summary, lines, question, tags, extra=None):
    out = [summary, ""]
    if extra:
        out += [extra, ""]
    out += lines + ["", question, "", tags]
    return "\n".join(out)


def part_desc(summary, story, part, universe, where, question, tags, extra=None):
    return desc(summary, ["This part:"] + [f"- Story: {story}", f"- Part: {part}", f"- Universe: {universe}", f"- Where: {where}"],
                question, tags, extra).replace("This part:\n- Story", "This part:\n- Story")


def fix_lines(text):
    """the list intro line stays outside the list: move it above the first '- ' line (already so) and return text."""
    return text


# three earlier descriptions per fixture, written by hand and different from each other
EARLIER = {
    "single1": [
        desc("A night shift nurse turns a spare room into a tiny bakery and sells out in a week.",
             ["The numbers:", "- Start: 40 loaves a day", "- Price: 3 dollars each", "- City: Leeds", "- Year: 2003"],
             "Would you quit your job for a bakery?", "#shorts #businessstory #bakery #2000s"),
        desc("Two brothers argue over a scrap yard and end up owning the whole street.",
             ["Quick facts:", "- Brothers: Sal and Dom", "- Place: Newark, New Jersey", "- Decade: the 1980s"],
             "Which brother was right in the end?", "#shorts #businessstory #scrapyard #brothers"),
        desc("A shy tailor finally says his price out loud to a stranger on a train.",
             ["On the train:", "- Tailor: Mr Ibrahim", "- Route: Cairo to Alexandria", "- Fee: one gold coin"],
             "Could you name your price to a stranger?", "#shorts #businessstory #tailor #trains"),
    ],
    "single2": [
        desc("A fisherman rows out at dusk and finds his net full of strange glass floats.",
             ["The night:", "- Who: old Tomas", "- Water: a cold bay in Norway", "- Catch: nine glass floats"],
             "Would you keep the floats or throw them back?", "#shorts #survivalstory #fishing #norway"),
        desc("Four climbers share one tent while the wind tears at the seams.",
             ["The camp:", "- Climbers: four friends", "- Height: 5,100 meters", "- Food: two days of soup"],
             "Who would you trust to keep watch?", "#shorts #survivalstory #climbing #basecamp"),
        desc("A girl follows a dry riverbed hoping it still leads to water.",
             ["The walk:", "- Girl: Amina, age 12", "- Land: the Sahel in July", "- Water: one bottle"],
             "Would you follow the river or wait for help?", "#shorts #survivalstory #desert #river"),
    ],
    "single3": [
        desc("A student sells handmade bracelets at a train station and learns what a margin is.",
             ["What she sold:", "- Item: beaded bracelets", "- Cost: 20 cents each", "- Price: 2 dollars", "- Place: Tokyo station"],
             "What would you sell at a train station?", "#shorts #businessstory #bracelets #tokyo"),
        desc("A plumber writes his phone number on every pipe he fixes and gets a call from a mayor.",
             ["The trick:", "- Plumber: Big Ray", "- Town: Galveston", "- Call: the mayor's wife"],
             "Would a number on a pipe work today?", "#shorts #businessstory #plumbing #galveston"),
        desc("Three friends rent a garage for a week and ship their first hundred orders.",
             ["The garage:", "- Friends: Lee, Ola and Priya", "- Rent: 90 dollars", "- Orders: one hundred"],
             "Would you share a garage with your friends?", "#shorts #businessstory #garage #startup"),
    ],
    "serial-part1": [
        desc("A lighthouse keeper writes down every ship that never arrives.",
             ["About the story:", "- Keeper: Elias", "- Coast: Cornwall", "- Season: winter"],
             "Would you keep writing in the dark?", "#shorts #survivalstory #lighthouse #storytime"),
        desc("Two sisters cross a frozen lake to reach a doctor.",
             ["About the walk:", "- Sisters: Ida and June", "- Lake: Lake Superior", "- Ice: thin near the shore"],
             "Would you trust the ice or go around?", "#shorts #survivalstory #frozenlake #sisters"),
        desc("A cook finds a locked door in the cellar of a mountain hut.",
             ["The hut:", "- Cook: Pablo", "- Mountain: the Andes", "- Door: iron, no handle"],
             "Would you open the door or leave it?", "#shorts #survivalstory #mountainhut #cellar"),
    ],
    "serial-mid": [
        part_desc("Nora misses the last ferry off a rock island with no phone signal and a storm coming.",
                  "The Last Ferry", 1, "Survival", "a rocky island off Maine, October",
                  "Would you wait at the dock or look for shelter first?", "#shorts #survivalstory #maine #storytime"),
        part_desc("Nora finds a cold stone hut and a stack of old fishing nets.",
                  "The Last Ferry", 2, "Survival", "the east side of the island",
                  "Would you burn the nets for warmth or save them?", "#shorts #survivalstory #stonehut #fishingnets",
                  "Part 1 is on the channel if you missed how it started."),
        desc("A trapper hears wolves closer than ever and counts his last matches.",
             ["The cold:", "- Trapper: Jon", "- Matches: six", "- Place: Yukon"],
             "Would you stay by the fire or move on?", "#shorts #survivalstory #yukon #wolves"),
    ],
    "serial-final": [
        part_desc("Dev is seventeen, has 212 dollars and an idea for selling websites to local shops.",
                  "The Website Kid", 1, "Entrepreneur", "Columbus, Ohio, March 1994",
                  "Would you have named a price on the spot?", "#shorts #businessstory #1990s #storytime"),
        part_desc("Dev learns that the diner owner wants a menu page and a map, not a speech.",
                  "The Website Kid", 4, "Entrepreneur", "the back booth of a diner",
                  "Would you have said yes to a rush job?", "#shorts #businessstory #diner #webdesign",
                  "Part 1 is on the channel if you want to see where it began."),
        desc("A florist swaps a year of free roses for a shop sign painted by a neighbor.",
             ["The swap:", "- Florist: Mrs Okoye", "- Painter: her neighbor", "- Term: twelve months"],
             "Would you trade a year of work for a sign?", "#shorts #businessstory #florist #swap"),
    ],
}


def inputs() -> dict:
    brand_s = {"display_name": "Gabryverse", "handle": "@gabryverse"}
    base = lambda name, run, summary, hook1, lines, beats, facts, tags: {
        "run_id": run, "channel": "scenarios", "summary": summary, "hook1": hook1, "script_lines": lines,
        "beats": [{"label": l, "narration": n} for l, n in beats], "facts": facts, "brand": brand_s,
        "export": {"caption_max": 100, "description_max": 1000, "hashtags": 4, "required_hashtags": tags, "pinned_comment": True},
        "earlier_descriptions": EARLIER[name], "needs_review": [],
    }
    out = {}
    out["single1"] = base("single1", "20261109-0101-first-website",
                          "A teenager talks a diner owner into paying 212 dollars for his first website.",
                          "A seventeen year old sold his first website for 212 dollars.",
                          ["He had a borrowed laptop and no clients.", "The diner owner laughed, then asked what it cost.", "He said 212 dollars and held his breath."],
                          [("Setup", "A teenager with a borrowed laptop walks into a diner."), ("Turn", "The owner laughs, then asks the price."), ("Payoff", "212 dollars, paid in cash.")],
                          [{"claim": "Early small business websites often sold for a few hundred dollars in the mid 1990s", "url": "https://example.org/web-history", "checked": "2026-11-09"}],
                          ["#shorts", "#businessstory"])
    out["single2"] = base("single2", "20261109-0102-radio-storm",
                          "A stranded hiker hears a radio crackle to life after three days alone in a storm.",
                          "Three days into the storm, the radio finally clicked on.",
                          ["Mara had not heard a voice in three days.", "Then the radio clicked.", "It said her name."],
                          [("Setup", "Mara is pinned on a ridge by a storm."), ("Turn", "The radio clicks on by itself."), ("Payoff", "A voice says her name.")],
                          [], ["#shorts", "#survivalstory"])
    out["single3"] = base("single3", "20261109-0103-pizza-payroll",
                          "A broke founder pays his very first hire in pizza and a promise.",
                          "A broke founder paid his first hire in pizza.",
                          ["There was no money for a salary.", "So he ordered twelve pizzas.", "And promised the rest later."],
                          [("Setup", "A founder with an empty bank account needs help."), ("Turn", "He pays in pizza."), ("Payoff", "The hire stays for nine years.")],
                          [], ["#shorts", "#businessstory"])
    ferry = {"story_title": "The Last Ferry", "universe": "Survival"}
    out["serial-part1"] = base("serial-part1", "20261109-0104-ferry-1",
                               "Nora misses the last ferry off a rock island with a storm coming.",
                               "The ferry left without her.",
                               ["Nora ran down the dock.", "The ferry was already a white dot.", "The sky behind her turned black."],
                               [("Setup", "Nora runs for the last ferry."), ("Turn", "It leaves without her."), ("Cliffhanger", "A storm comes in.")],
                               [], ["#shorts", "#survivalstory"])
    out["serial-part1"]["serial"] = dict(ferry, part=1, final=False, earlier_titles=[])
    out["serial-mid"] = base("serial-mid", "20261109-0105-ferry-3",
                             "Nora hears an engine in the fog, but it is moving away from the island.",
                             "She heard a boat engine in the fog.",
                             ["Dawn was an hour away.", "The engine hummed somewhere past the rocks.", "Then it faded."],
                             [("Setup", "Nora waits on the north beach."), ("Turn", "An engine hums in the fog."), ("Cliffhanger", "It fades away.")],
                             [], ["#shorts", "#survivalstory"])
    out["serial-mid"]["serial"] = dict(ferry, part=3, final=False,
                                       earlier_titles=["The ferry left without her | The Last Ferry, Part 1", "Nobody lives in the stone hut | The Last Ferry, Part 2"])
    web = {"story_title": "The Website Kid", "universe": "Entrepreneur"}
    out["serial-final"] = base("serial-final", "20261109-0106-website-5",
                               "Dev finally names his price to the diner owner and learns what the first site was worth.",
                               "He finally named his price.",
                               ["Dev took a breath.", "He said the number out loud.", "The owner shook his hand."],
                               [("Setup", "Dev sits in the back booth."), ("Turn", "He says the number."), ("Payoff", "A handshake and a new beginning.")],
                               [{"claim": "The first web browsers for the public arrived in 1993", "url": "https://example.org/browsers", "checked": "2026-11-09"}],
                               ["#shorts", "#businessstory"])
    out["serial-final"]["serial"] = dict(web, part=5, final=True,
                                         earlier_titles=["Everyone laughed at his price | The Website Kid, Part 1", "A menu, a map and a deadline | The Website Kid, Part 4"])
    return out


def answers() -> dict:
    a = {}
    a["single1"] = {
        "title": "He sold his first website to a laughing diner owner for 212 dollars",
        "description": desc("A teenager with a borrowed laptop talks a diner owner into paying for his first website.",
                            ["What happens:", "- Who: a seventeen year old from Ohio", "- Price: 212 dollars, paid in cash", "- Place: a diner on a Tuesday morning", "- Year: 1996"],
                            "Would you have asked for more, or taken the cash and run?", "#shorts #businessstory #1990s #firstsale"),
        "pinned_comment": "What was the first thing you ever sold, and who bought it?",
        "hashtags": ["#shorts", "#businessstory", "#1990s", "#firstsale"]}
    a["single2"] = {
        "title": "The radio clicked on after three days of silence",
        "description": desc("A stranded hiker hears a radio crackle to life after three days alone in a storm.",
                            ["The setup:", "- Who: Mara, a solo hiker", "- Where: a ridge in the Cascades", "- Time: day three of a storm", "- Gear: one radio and half a flask of water"],
                            "Would you answer the voice or stay quiet?", "#shorts #survivalstory #cascades #stormcamp"),
        "pinned_comment": "Who do you think is on the other end of the radio?",
        "hashtags": ["#shorts", "#survivalstory", "#cascades", "#stormcamp"]}
    a["single3"] = {
        "title": "He paid his first employee in pizza and a promise",
        "description": desc("A founder with an empty bank account pays his very first hire in twelve pizzas.",
                            ["The deal:", "- Founder: Cal, twenty four", "- Pay: twelve pizzas", "- Promise: the rest later", "- Result: nine years together"],
                            "Would you work for pizza today, or ask for cash?", "#shorts #businessstory #firsthire #pizzapayroll"),
        "pinned_comment": "Would you take the pizza deal, or hold out for a salary?",
        "hashtags": ["#shorts", "#businessstory", "#firsthire", "#pizzapayroll"]}
    a["serial-part1"] = {
        "title": "The ferry left without her | The Last Ferry, Part 1",
        "description": desc("Nora runs for the last ferry off a rock island and watches it leave without her.",
                            ["This part:", "- Story: The Last Ferry", "- Part: 1", "- Universe: Survival", "- Where: a small island off Maine, October"],
                            "Would you wait at the dock or find shelter first?", "#shorts #survivalstory #maine #stranded"),
        "pinned_comment": "Dock or shelter: what would you do first?\nThe next part is coming soon.",
        "hashtags": ["#shorts", "#survivalstory", "#maine", "#stranded"]}
    a["serial-mid"] = {
        "title": "She heard a boat engine in the fog | The Last Ferry, Part 3",
        "description": desc("Nora hears an engine in the fog, but the sound is moving away from the island.",
                            ["This part:", "- Story: The Last Ferry", "- Part: 3", "- Universe: Survival", "- Where: the north beach before dawn"],
                            "Would you shout for help or stay hidden?", "#shorts #survivalstory #fogbound #lastferry",
                            extra="Part 1 is on the channel if you just found this story."),
        "pinned_comment": "Would you shout into the fog or stay hidden?\nPart 4 is the next part, coming soon.",
        "hashtags": ["#shorts", "#survivalstory", "#fogbound", "#lastferry"]}
    a["serial-final"] = {
        "title": "He finally named his price | The Website Kid, Part 5",
        "description": desc("Dev sits in the back booth and finally says his number out loud to the diner owner.",
                            ["This part:", "- Story: The Website Kid", "- Part: 5", "- Universe: Entrepreneur", "- Where: a diner in Columbus, Ohio"],
                            "Was the number fair, or too low?", "#shorts #businessstory #webdesign #finalpart",
                            extra="Part 1 is on the channel, and it shows how this started."),
        "pinned_comment": "Was his price fair, or did he leave money on the table?",
        "hashtags": ["#shorts", "#businessstory", "#webdesign", "#finalpart"]}
    return a


def write_json(path, data) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def write_fixtures(dest: str) -> None:
    os.makedirs(dest, exist_ok=True)
    ins, ans = inputs(), answers()
    for name in NAMES:
        write_json(os.path.join(dest, f"{name}.json"), ins[name])
        write_json(os.path.join(dest, f"answer-ok-{name}.json"), ans[name])


# ------------------------------------------------------------------------------------------------ self-test

class Runner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.mod = load_exporter()
        self.tmp = tempfile.mkdtemp(prefix="m19-ytshorts-")
        self.n = 0

    def result(self, ok: bool, name: str, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"PASS {name}")
        else:
            self.failed += 1
            print(f"FAIL {name}" + (f": {detail}" if detail else ""))

    def cli(self, *argv):
        """(exit code, stdout text) of the exporter's main(), in-process."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self.mod.main(list(argv))
        return code, buf.getvalue()

    def file(self, data, name=None) -> str:
        self.n += 1
        path = os.path.join(self.tmp, name or f"t{self.n}.json")
        write_json(path, data)
        return path

    def check(self, inp, ans) -> list:
        code, out = self.cli("check", "--input", self.file(inp), "--answer", self.file(ans))
        return json.loads(out)["errors"] if code == 0 else [f"exit {code}"]

    def expect_error(self, name, inp, ans, needle, only=False) -> None:
        errs = self.check(inp, ans)
        hit = any(needle in e for e in errs)
        ok = hit and (not only or len(errs) == 1)
        self.result(ok, name, f"wanted '{needle}', got {errs}")


def mutate(ans, **kw):
    out = dict(ans)
    out.update(kw)
    return out


def run_selftest() -> int:
    r = Runner()
    ins, ans = inputs(), answers()
    try:
        # fixtures and their good answers
        d = os.path.join(r.tmp, "fixtures")
        write_fixtures(d)
        for name in NAMES:
            ok = all(os.path.isfile(os.path.join(d, f)) for f in (f"{name}.json", f"answer-ok-{name}.json"))
            r.result(ok, f"fixtures: {name} and answer-ok-{name} written")
        for name in NAMES:
            code, out = r.cli("check", "--input", os.path.join(d, f"{name}.json"), "--answer", os.path.join(d, f"answer-ok-{name}.json"))
            res = json.loads(out)
            r.result(code == 0 and res["ok"] and not res["errors"], f"check passes the good answer of {name}", str(res.get("errors")))
        # the same through a real subprocess once (the CLI the runner uses)
        p = subprocess.run([sys.executable, EXPORTER_PATH, "check", "--input", os.path.join(d, "serial-mid.json"),
                            "--answer", os.path.join(d, "answer-ok-serial-mid.json")], capture_output=True, text=True, encoding="utf-8")
        r.result(p.returncode == 0 and json.loads(p.stdout)["ok"] and "\r" not in p.stdout, "subprocess check prints JSON with LF", p.stdout + p.stderr)

        s1, a1 = ins["single1"], ans["single1"]
        good_desc = a1["description"]
        before_tags = good_desc.rsplit("\n\n", 1)[0]

        # planted faults, each its own check
        long_desc = before_tags + "\n\n" + "\n".join("Another short line about the place and the year and the people." for _ in range(12)) + "\n\n#shorts #businessstory #1990s #firstsale"
        r.expect_error("fault: 1100-character description fails the length check", s1, mutate(a1, description=long_desc), "description is ")
        errs = r.check(s1, mutate(a1, description=long_desc))
        r.result(len(long_desc) > 1000 and any("limit is 1000" in e for e in errs), "fault: that description is over 1000 characters", str(len(long_desc)))
        five = before_tags + "\n\n#shorts #businessstory #1990s #firstsale #ohio"
        r.expect_error("fault: a line of 5 hashtags", s1, mutate(a1, description=five), "ends with 5 hashtags, it must be exactly 4")
        para = "He walked in with a borrowed laptop and no clients at all and talked for what felt like an hour about a thing the owner did not understand yet, " \
               "while the owner kept laughing and pouring coffee for the other tables in the room, until the room went quiet and everybody listened to him say the price. " \
               "Nobody expected a teenager to say it so clearly and so calmly, and he never looked away from the owner while he did it, not once during the whole minute."
        paragraph_desc = good_desc.replace("\n\nWould you have asked", "\n\n" + para + "\n\nWould you have asked")
        r.result(len(para) >= 400, "fault: the planted paragraph is 400 characters or more", str(len(para)))
        r.expect_error("fault: a 400-character paragraph", s1, mutate(a1, description=paragraph_desc), "description has a paragraph of")
        nolist = "\n".join(ln[2:] if ln.startswith("- ") else ln for ln in good_desc.split("\n"))
        r.expect_error("fault: a description without a list", s1, mutate(a1, description=nolist), "description has no list of 3 to 6 lines")
        two = "\n".join(ln for ln in good_desc.split("\n") if not ln.startswith("- Place") and not ln.startswith("- Year"))
        r.expect_error("fault: a list of only 2 items", s1, mutate(a1, description=two), "description has no list of 3 to 6 lines")
        copy = s1["earlier_descriptions"][0]
        r.expect_error("fault: a copy of an earlier description (first line)", s1, mutate(a1, description=copy), "first line matches the first line of earlier description 1")
        r.expect_error("fault: a copy of an earlier description (overlap)", s1, mutate(a1, description=copy), "description overlaps 100 percent with earlier description 1")
        reworded = good_desc.replace(good_desc.split("\n")[0], "Some other opening sentence about a different thing entirely.")
        mixed = reworded + "\n"
        mixed_in = dict(s1)
        mixed_in["earlier_descriptions"] = [good_desc.split("\n\n#")[0] + "\n\n#shorts #a #b #c"]
        r.expect_error("fault: trigram overlap above 30 percent without the same first line", mixed_in, mutate(a1, description=mixed), "description overlaps")

        # titles
        r.expect_error("fault: a 160-character title fails at caption_max 150", dict(s1, export=dict(s1["export"], caption_max=150)),
                       mutate(a1, title=("The diner owner laughed " * 7)[:160].strip().ljust(160, "x")), "title is 160 characters, the limit is 150")
        r.expect_error("fault: a 120-character title fails at caption_max 100", s1, mutate(a1, title=("x" * 120)), "title is 120 characters, the limit is 100")
        r.expect_error("fault: a title of 101 characters fails at caption_max 100", s1, mutate(a1, title="y" * 101), "title is 101 characters, the limit is 100")
        r.expect_error("fault: a title with two lines", s1, mutate(a1, title="One line\nTwo lines"), "title is more than one line")
        r.expect_error("fault: a hashtag in the title", s1, mutate(a1, title="He sold a site #shorts"), "title contains a hashtag")
        r.expect_error("fault: a link in the title", s1, mutate(a1, title="He sold a site at example.com"), "title contains a link")
        r.expect_error("fault: a link in the description", s1, mutate(a1, description=good_desc.replace("Would you", "See https://example.com. Would you")), "description contains a link")
        r.expect_error("fault: a link in the pinned comment", s1, mutate(a1, pinned_comment="Where did you see it? www.example.com"), "pinned comment contains a link")

        # the description's other rules
        r.expect_error("fault: first line repeats the title", s1, mutate(a1, title="A teenager with a borrowed laptop talks a diner owner into paying for his first website."),
                       "first line repeats the title")
        two_sent = good_desc.replace("paying for his first website.", "paying for his first website. It goes better than he feared.")
        r.expect_error("fault: first line with two sentences", s1, mutate(a1, description=two_sent), "first line is more than one sentence")
        r.expect_error("fault: required hashtag missing", s1, mutate(a1, description=good_desc.replace("#shorts", "#short")), "required hashtag #shorts is missing")
        mid_tag = good_desc.replace("What happens:", "What happens #diner:")
        r.expect_error("fault: a hashtag outside the last line", s1, mutate(a1, description=mid_tag), "hashtag outside its last line")
        r.expect_error("fault: hashtags two spaces apart", s1, mutate(a1, description=good_desc.replace("#shorts #businessstory", "#shorts  #businessstory")), "separated by single spaces")
        r.expect_error("fault: a description that does not end with hashtags", s1, mutate(a1, description=good_desc + "\nThanks for watching"), "does not end with a hashtag line")
        r.expect_error("fault: an em dash left in the description (check)", s1, mutate(a1, description=good_desc.replace("Would you", "Wait " + EM_DASH + " would you")), "description contains an em dash")
        r.expect_error("fault: a slop word left in the description (check)", s1, mutate(a1, description=good_desc.replace("What happens:", "Let us delve into what happens:")), "description contains slop words")
        r.expect_error("fault: the hashtags field disagrees with the description", s1, mutate(a1, hashtags=["#shorts", "#businessstory", "#other", "#more"]), "hashtags field does not match")

        # pinned comment
        r.expect_error("fault: pinned comment over 200 characters", s1, mutate(a1, pinned_comment="Would you do it? " + "x" * 200), "pinned comment is ")
        r.expect_error("fault: pinned comment without a question", s1, mutate(a1, pinned_comment="Tell me about your first sale."), "pinned comment asks no question")
        r.expect_error("fault: empty pinned comment", s1, mutate(a1, pinned_comment=""), "pinned comment is empty")
        off = dict(s1, export=dict(s1["export"], pinned_comment=False))
        r.result(r.check(off, mutate(a1, pinned_comment="")) == [], "a channel with pinned_comment false needs none")

        # serial rules
        m_in, m_a = ins["serial-mid"], ans["serial-mid"]
        r.expect_error("fault: serial title without the story suffix", m_in, mutate(m_a, title="She heard a boat engine in the fog"), 'title of a serial part must read')
        r.expect_error("fault: serial title with a wrong part number", m_in, mutate(m_a, title="She heard a boat engine in the fog | The Last Ferry, Part 2"), 'title of a serial part must read')
        r.expect_error("fault: serial title with no hook phrase", m_in, mutate(m_a, title="| The Last Ferry, Part 3"), "title has no hook phrase")
        of_in = dict(m_in, serial=dict(m_in["serial"], story_title="The Last Ferry, Part 3 of 5"))
        r.expect_error("fault: serial title states the part count (Part 3 of 5)", of_in, mutate(m_a, title="She heard an engine | The Last Ferry, Part 3 of 5, Part 3"), "title states a part count")
        r.expect_error("fault: Part 1 line missing from Part 3", m_in, mutate(m_a, description=m_a["description"].replace("Part 1 is on the channel if you just found this story.\n\n", "")),
                       "from Part 2 on needs one line")
        r.expect_error("fault: Part 1 only in a list item does not count", m_in, mutate(m_a, description=m_a["description"].replace("Part 1 is on the channel if you just found this story.", "- Part 1 is on the channel")),
                       "from Part 2 on needs one line")
        r.expect_error("fault: non-final pinned comment without a next-part line", m_in, mutate(m_a, pinned_comment="Would you shout into the fog or stay hidden?"), "needs a second line saying the next part is coming")
        f_in, f_a = ins["serial-final"], ans["serial-final"]
        r.expect_error("fault: final pinned comment saying a next part is coming", f_in, mutate(f_a, pinned_comment="Was his price fair, or too low?\nThe next part is coming soon."),
                       "final part must not say a next part is coming")
        p_in = ins["serial-part1"]
        r.result(r.check(p_in, mutate(ans["serial-part1"], description=ans["serial-part1"]["description"].replace("Nora runs", "Part 1 is on the channel. Nora runs"))) is not None,
                 "Part 1 may mention itself without error")

        # a clean answer has no errors, and the same text with a mistake gets exactly its own error (nothing else)
        r.expect_error("fault: only the length error for a long description", s1, mutate(a1, description=long_desc), "description is ", only=False)

        # compose: humanize first, then the rewrite flow
        out_path = os.path.join(r.tmp, "export.json")
        dirty = {"title": "He sold his first website to a laughing diner owner for 212 dollars",
                 "description": good_desc.replace("- Who:", "\u2022 Who:").replace("- Price:", "* Price:").replace("- Place:", "  - Place:").replace(
                     "What happens:", "What happens " + EM_DASH + " in short:").replace("borrowed laptop", "borrowed laptop and a robust plan"),
                 "pinned_comment": a1["pinned_comment"], "hashtags": a1["hashtags"]}
        code, out = r.cli("compose", "--input", r.file(s1), "--answer", r.file(dirty), "--out", out_path)
        res = json.loads(out)
        man = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
        r.result(code == 0 and res["ok"] and res["written"] and EM_DASH not in man.get("description", "") and "- Who: a seventeen" in man.get("description", "")
                 and "- Price: 212" in man.get("description", "") and "\n- Place:" in man.get("description", "") and "robust" not in man.get("description", ""),
                 "compose humanizes (em dash, bullets, indents, slop) before checking", f"{res} {man.get('description')}")
        r.result(man.get("needs_review") == [] and man.get("files") == {"reel": ""} and man.get("hooks") == {"hook1": s1["hook1"]} and man.get("story") is None
                 and man.get("upload_steps") == [] and "solution" not in man and man.get("hashtags") == a1["hashtags"], "compose manifest fields for a single video", json.dumps(man)[:300])
        if os.path.exists(out_path):
            os.remove(out_path)
        bad = mutate(a1, description=five)
        code, out = r.cli("compose", "--input", r.file(s1), "--answer", r.file(bad), "--out", out_path)
        res = json.loads(out)
        r.result(code == 0 and res["ok"] is False and res["errors"] and not os.path.exists(out_path) and res.get("written") is False, "rewrite flow 1: a bad answer without --force returns ok false and writes nothing", str(res))
        code, out = r.cli("compose", "--input", r.file(s1), "--answer", r.file(a1), "--out", out_path)
        res = json.loads(out)
        r.result(code == 0 and res["ok"] and os.path.exists(out_path), "rewrite flow 2: the good answer then passes")
        os.remove(out_path)
        with_review = dict(s1, needs_review=["S12: something earlier"])
        code, out = r.cli("compose", "--input", r.file(with_review), "--answer", r.file(bad), "--out", out_path, "--force", "--reel", "C:/x/final.mp4")
        res = json.loads(out)
        man = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
        nr = man.get("needs_review") or []
        r.result(res.get("forced") is True and res.get("written") is True and nr[:1] == ["S12: something earlier"] and len(nr) == 1 + len(res["errors"])
                 and all(x.startswith("youtube-shorts exporter: ") for x in nr[1:]) and any("exactly 4" in x for x in nr) and man["files"]["reel"] == "C:/x/final.mp4",
                 "compose --force keeps the failures as NEEDS REVIEW lines after the input's own", str(nr))
        # no title ever exceeds caption_max, on every fixture
        over = []
        for name in NAMES:
            op = os.path.join(r.tmp, f"export-{name}.json")
            code, out = r.cli("compose", "--input", os.path.join(d, f"{name}.json"), "--answer", os.path.join(d, f"answer-ok-{name}.json"), "--out", op)
            res = json.loads(out)
            m2 = json.load(open(op, encoding="utf-8"))
            if not res["ok"] or len(m2["title"]) > ins[name]["export"]["caption_max"] or len(m2["description"]) > ins[name]["export"]["description_max"]:
                over.append(name)
            r.result(res["ok"] and m2["checks"]["ok"], f"compose passes {name}", str(res.get("errors")))
        r.result(not over, "no composed title exceeds caption_max and no description exceeds description_max", str(over))
        # serial manifest
        m2 = json.load(open(os.path.join(r.tmp, "export-serial-mid.json"), encoding="utf-8"))
        r.result(m2["story"] == "The Last Ferry" and m2["part"] == 3 and m2["upload_steps"] == ['set the related video to "The Last Ferry, Part 2"', 'add this part to the playlist "The Last Ferry"'],
                 "serial manifest: story, part and the two upload steps from Part 2", str(m2["upload_steps"]))
        m1 = json.load(open(os.path.join(r.tmp, "export-serial-part1.json"), encoding="utf-8"))
        r.result(m1["upload_steps"] == ['add this part to the playlist "The Last Ferry"'], "serial manifest: Part 1 has only the playlist step", str(m1["upload_steps"]))

        # render
        cap = r.mod.render_captions(m2, "scenarios", 7, "20261109-0105-ferry-3")
        lines = cap.split("\n")
        want_order = ["STORY", "TITLE", "DESCRIPTION", "PINNED COMMENT", "UPLOAD STEPS", "HOOKS", "RUN"]
        heads = [ln for ln in lines if ln in want_order or ln in ("NEEDS REVIEW", "FACTS AND SOURCES", "EDITOR")]
        r.result(heads == want_order, "render: serial sections in the order of the spec (no NEEDS REVIEW, no facts)", str(heads))
        r.result(lines[0] == "STORY" and lines[1] == "The Last Ferry, Part 3" and 'scenarios-7.mp4 uses: "She heard a boat engine in the fog."' in lines
                 and "channels/scenarios/runs/20261109-0105-ferry-3" in lines and '- add this part to the playlist "The Last Ferry"' in lines and cap.endswith("\n") and "\r" not in cap and EM_DASH not in cap,
                 "render: serial lines (story, part, hooks, run, upload steps, LF, no em dash)", cap[:200])
        single_man = json.load(open(os.path.join(r.tmp, "export-single1.json"), encoding="utf-8"))
        cap1 = r.mod.render_captions(single_man, "scenarios", 2, "run1")
        h1 = [ln for ln in cap1.split("\n") if ln in want_order + ["NEEDS REVIEW", "FACTS AND SOURCES"]]
        r.result(h1 == ["TITLE", "DESCRIPTION", "PINNED COMMENT", "HOOKS", "FACTS AND SOURCES", "RUN"] and "STORY" not in h1 and "UPLOAD STEPS" not in h1
                 and "- Early small business websites often sold for a few hundred dollars in the mid 1990s: https://example.org/web-history (checked 2026-11-09)" in cap1,
                 "render: a single video has no STORY or UPLOAD STEPS, facts as sources", str(h1))
        no_pin = dict(single_man, pinned_comment="")
        r.result("PINNED COMMENT" not in r.mod.render_captions(no_pin, "scenarios", 2, "run1"), "render: no PINNED COMMENT section when it is empty")
        flagged = dict(single_man, needs_review=["youtube-shorts exporter: x"])
        r.result("NEEDS REVIEW\nyoutube-shorts exporter: x" in r.mod.render_captions(flagged, "scenarios", 2, "run1"), "render: NEEDS REVIEW only when flagged, lines as they are")
        mpath = os.path.join(r.tmp, "export-serial-mid.json")
        code, out = r.cli("render", "--export", mpath, "--id", "scenarios", "--number", "7", "--run-id", "20261109-0105-ferry-3")
        r.result(code == 0 and out == cap, "render: the CLI prints the same text as render_captions")

        # data
        for name in NAMES:
            dp = os.path.join(r.tmp, f"data-{name}.json")
            code, out = r.cli("data", "--input", os.path.join(d, f"{name}.json"), "--out", dp)
            dd = json.load(open(dp, encoding="utf-8"))
            need = ["summary", "hook1", "script", "beats", "facts", "title_rule", "pinned_rule", "part_rule", "hashtag_rule", "serial_block", "earlier_openers", "earlier_descriptions"]
            r.result(code == 0 and json.loads(out)["ok"] and all(k in dd for k in need) and dd["serial"] == name.startswith("serial") and EM_DASH not in json.dumps(dd, ensure_ascii=False),
                     f"data: prompt data for {name}")
        dd = json.load(open(os.path.join(r.tmp, "data-serial-final.json"), encoding="utf-8"))
        r.result(dd["part"] == 5 and dd["final"] is True and dd["story_title"] == "The Website Kid" and dd["title_suffix"] == "The Website Kid, Part 5"
                 and "no line says a next part is coming" in dd["pinned_rule"], "data: the serial part's facts and the final part's pinned rule")
        bad_in = dict(s1)
        del bad_in["hook1"]
        code, out = r.cli("data", "--input", r.file(bad_in), "--out", os.path.join(r.tmp, "data-bad.json"))
        r.result(code == 2, "data: an input that breaks input.schema.json exits 2")
        bad_in2 = dict(s1, serial={"story_title": "X", "part": "two", "final": False})
        code, out = r.cli("check", "--input", r.file(bad_in2), "--answer", r.file(a1))
        r.result(json.loads(out)["ok"] is False and "input.json" in json.loads(out)["errors"][0], "check: an invalid serial block is reported as an input problem")

        # record
        rp = os.path.join(r.tmp, "logs", "descriptions.jsonl")
        for _ in range(2):
            r.cli("record", "--input", r.file(s1), "--export", os.path.join(r.tmp, "export-single1.json"), "--descriptions", rp)
        rows = [json.loads(x) for x in open(rp, encoding="utf-8").read().split("\n") if x.strip()]
        r.result(len(rows) == 1 and set(rows[0]) == {"run_id", "title", "description", "date"} and rows[0]["run_id"] == s1["run_id"], "record: one line per run id, idempotent", str(rows))
        r.cli("record", "--input", r.file(ins["single2"]), "--export", os.path.join(r.tmp, "export-single2.json"), "--descriptions", rp)
        r.result(len(open(rp, encoding="utf-8").read().strip().split("\n")) == 2, "record: another run id appends")

        # files of the exporter: no em dash, LF only
        folder = os.path.join(REPO, "pipeline", "platforms", "youtube-shorts")
        mine = [os.path.join(folder, f) for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))] + [os.path.abspath(__file__)]
        bad_files = []
        for path in mine:
            raw = open(path, "rb").read()
            if b"\r" in raw or bytes([0xE2, 0x80, 0x94]) in raw:
                bad_files.append(os.path.basename(path))
        r.result(not bad_files, "the exporter's files hold no em dash and no CRLF", str(bad_files))
    finally:
        shutil.rmtree(r.tmp, ignore_errors=True)
    print(f"RESULT: {r.passed} passed, {r.failed} failed")
    return 1 if r.failed else 0


def main(argv=None) -> int:
    setup_streams()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["fixtures"] and len(argv) == 2:
        write_fixtures(argv[1])
        print(f"wrote {len(NAMES)} inputs and answers to {argv[1]}")
        return 0
    if argv[:1] == ["selftest"]:
        return run_selftest()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
