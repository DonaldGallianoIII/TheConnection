"""
A fixture mailbox for tests/test_report.py (C7, D42): twelve messages
among four made-up names, written by hand under a TcRoot's TC_ROOT with
fixed headers, file times and read-time records, so every fact the report
draws is known here exactly.

Model:  Claude Opus 5.5 (the DASH lane agent), 2026-10-17
Status: unreviewed

The names: annika (an orchestrator by card), bertil and corwin (workers
that report to annika by card), and dagny, who only sends: no card and no
inbox, so C5 gives dagny no role and the scrub calls dagny `session-1`.

Plants, each a word no real output may hold: a word after a tag on a
first body line (SECRET_AFTER_TAG), a word on a second body line
(SECRET_SECOND_LINE), a header note (SECRET_NOTE), a card field other
than reports_to (SECRET_CARD), a status file (SECRET_STATUS), and a tag
off the scrub's allow list (PLANTED_TAG), which only the unscrubbed page
may show.

Message 10's header does not parse, so it is left out of every time
chart and counted in words.

@interacts  writes mail/, cards/ and status/ under the root it is given
            (a TcRoot's throwaway TC_ROOT, never a live mailbox): one file
            per message, one read/.read-times per read/, one card per
            carded name, one status file; sets each message file's times.
@deps       python3 stdlib (collections, datetime, json, os).
@complexity O(m) over m = 12 messages (17 for the three-day mailbox).
@alloc      the files, removed with the TcRoot.

WINDOW (Claude Opus 5.5, unreviewed): a second, three-day mailbox for
the time window (C7, D44), WINDOW_MESSAGES, built by the same build().
"""

import collections
import datetime
import json
import os

# The fixture's first message, and every other time an offset from it.
BASE = datetime.datetime(2026, 10, 1, 9, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=-5)))
MINUTE = 60
HOUR = 60 * MINUTE

SECRET_AFTER_TAG = "SECRETWORDA"
SECRET_SECOND_LINE = "SECONDLINEPLANT"
SECRET_NOTE = "NOTEPLANT"
SECRET_CARD = "ACCOUNTPLANT"
SECRET_STATUS = "STATUSPLANT"
PLANTED_TAG = "ZEBRAPLANT"
SECRETS = (SECRET_AFTER_TAG, SECRET_SECOND_LINE, SECRET_NOTE, SECRET_CARD, SECRET_STATUS)
NAMES = ("annika", "bertil", "corwin", "dagny")

# One message: its number, sender, recipient, sent offset (None: a header
# that does not parse), read offset (None: unread, still in its inbox),
# body, and header note.
Spec = collections.namedtuple("Spec", "number sender to sent read body note")

MESSAGES = (
    Spec(1, "annika", "bertil", 0, 5 * MINUTE, "PLAN: build the parser", None),
    Spec(2, "bertil", "annika", 10 * MINUTE, 12 * MINUTE, f"QUESTION #1 which format {SECRET_AFTER_TAG}", None),
    Spec(3, "annika", "bertil", 20 * MINUTE, HOUR, "ANSWER re #2: json", None),
    Spec(4, "bertil", "annika", 2 * HOUR, 2 * HOUR + 20 * MINUTE, "Re #3: thanks", None),
    Spec(5, "corwin", "annika", 3 * HOUR, None, f"{PLANTED_TAG}: status", None),
    Spec(6, "annika", "corwin", 3 * HOUR + 30 * MINUTE, 4 * HOUR, "#5 got it", None),
    Spec(7, "annika", "corwin", 4 * HOUR + 10 * MINUTE, None, "Re #6: one more", None),
    Spec(8, "bertil", "annika", 5 * HOUR, 5 * HOUR + 30 * MINUTE, "ANSWER sure", None),
    Spec(9, "dagny", "bertil", 6 * HOUR, 6 * HOUR + MINUTE, "FYI hello", None),
    Spec(10, "bertil", "corwin", None, None, "STATUS: odd header", None),
    Spec(11, "annika", "bertil", 16 * HOUR, None, f"STATUS: fine\n{SECRET_SECOND_LINE} here",
         f"via ssh gate, key {SECRET_NOTE}"),
    Spec(12, "corwin", "annika", 17 * HOUR, None, "QUESTION when?", None),
)

# Cards: name to reports_to (None for none). dagny has none at all.
CARDS = {"annika": None, "bertil": "annika", "corwin": "annika"}
# The inboxes build() makes: every recipient's, and only those.
INBOXES = ("annika", "bertil", "corwin")

# ---------- the three-day mailbox, for the time window (C7, D44) ----------
# WINDOW (Claude Opus 5.5, unreviewed): seventeen messages over three
# days, 2026-10-01 to 2026-10-03 at BASE's offset (-05:00), among annika,
# bertil and corwin (carded as above) and eskil, who has an inbox and no
# card, so C5 infers eskil's role from mail alone. The middle day runs
# from DAY_TWO to DAY_THREE. Facts the window tests lean on:
# - corwin mails first on day two (7), so the window's first-mail order,
#   and its scrub labels, differ from the whole history's;
# - over the whole history eskil splits between bertil (3, 4, 5) and
#   annika (10, 11, 12, 14) and gets no inferred parent (a peer); on day
#   two alone eskil mails only annika, so eskil is a worker under annika
#   by inference, and annika an orchestrator by inference;
# - 8, on day two, names 2, on day one, and runs back from 2's recipient
#   to its sender: a reply to a message before the window;
# - 13, a MERGE ask on day two, is read on day three and answered on day
#   three (15): its read time stays, its answer is outside the window;
# - corwin's 6 (day one, 22:00) and 7 (day two, 01:00) are three hours
#   apart: a quiet stretch over the whole history, none in the window;
# - 17's header does not parse: no sent time, outside any window.
DAY_TWO = 15 * HOUR
DAY_THREE = 39 * HOUR
WINDOW_MESSAGES = (
    Spec(1, "annika", "bertil", 0, 5 * MINUTE, "PLAN: day one", None),
    Spec(2, "bertil", "annika", HOUR, HOUR + 20 * MINUTE, "QUESTION which format", None),
    Spec(3, "eskil", "bertil", 2 * HOUR, 2 * HOUR + 10 * MINUTE, "FYI hello", None),
    Spec(4, "bertil", "eskil", 3 * HOUR, 3 * HOUR + 5 * MINUTE, "FYI hello back", None),
    Spec(5, "eskil", "bertil", 4 * HOUR, 4 * HOUR + 30 * MINUTE, "STATUS: fine", None),
    Spec(6, "corwin", "annika", 13 * HOUR, 13 * HOUR + 30 * MINUTE, "STATUS: late", None),
    Spec(7, "corwin", "annika", 16 * HOUR, 17 * HOUR, "QUESTION still on?", None),
    Spec(8, "annika", "bertil", 17 * HOUR, 18 * HOUR, "ANSWER re #2: json", None),
    Spec(9, "annika", "corwin", 18 * HOUR, 19 * HOUR, "ANSWER re #7: yes", None),
    Spec(10, "eskil", "annika", 20 * HOUR, 20 * HOUR + 10 * MINUTE, "QUESTION may I", None),
    Spec(11, "annika", "eskil", 21 * HOUR, 21 * HOUR + 5 * MINUTE, "Re #10: yes", None),
    Spec(12, "eskil", "annika", 23 * HOUR, 23 * HOUR + 20 * MINUTE, "FYI thanks", None),
    Spec(13, "corwin", "annika", 26 * HOUR, 40 * HOUR, "MERGE ready", None),
    Spec(14, "eskil", "annika", 30 * HOUR, None, "FYI one more", None),
    Spec(15, "annika", "corwin", 40 * HOUR, None, "ANSWER re #13: merged", None),
    Spec(16, "bertil", "annika", 45 * HOUR, 46 * HOUR, "DONE", None),
    Spec(17, "bertil", "corwin", None, None, "STATUS: odd header", None),
)
WINDOW_INBOXES = ("annika", "bertil", "corwin", "eskil")
WINDOW_NAMES = ("annika", "bertil", "corwin", "eskil")


def at(offset):
    """The fixture's time `offset` seconds after BASE, as a message header writes it.

    @interacts  none.
    @deps       datetime; BASE.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return (BASE + datetime.timedelta(seconds=offset)).isoformat(timespec="seconds")


def build(root, messages=MESSAGES, inboxes=INBOXES):
    """Write the fixture mailbox under `root` (a pathlib.Path: a TcRoot's path): `messages` (MESSAGES, or WINDOW_MESSAGES for the three-day mailbox) into `inboxes`, with CARDS and the status file either way.

    @interacts  see the module block.
    @deps       json, os; MESSAGES, INBOXES, CARDS, at.
    @complexity O(m) over m messages.
    @alloc      the files.
    """
    mail = root / "mail"
    for name in inboxes:
        (mail / f"to-{name}" / "read").mkdir(parents=True, exist_ok=True)
    records = {}
    for spec in messages:
        name = f"{spec.number:06d}-from-{spec.sender}.md"
        folder = mail / f"to-{spec.to}" / ("read" if spec.read is not None else "")
        if spec.sent is None:
            header = f"# message {spec.number}, header lost"
        else:
            header = f"# #{spec.number} from {spec.sender} to {spec.to}, {at(spec.sent)}"
            if spec.note:
                header += f", {spec.note}"
        path = folder / name
        path.write_text(f"{header}\n\n{spec.body}\n", encoding="utf-8")
        stamp = (BASE + datetime.timedelta(seconds=spec.sent or 0)).timestamp()
        os.utime(path, (stamp, stamp))
        if spec.read is not None:
            records.setdefault(spec.to, []).append({"name": name, "number": spec.number, "read": at(spec.read)})
    for to, lines in records.items():
        text = "".join(json.dumps(line) + "\n" for line in lines)
        (mail / f"to-{to}" / "read" / ".read-times").write_text(text, encoding="utf-8")
    cards = root / "cards"
    cards.mkdir(exist_ok=True)
    for name, reports_to in CARDS.items():
        card = {"name": name, "kind": "claude", "account": SECRET_CARD, "route": "local"}
        if reports_to:
            card["reports_to"] = reports_to
        (cards / f"{name}.json").write_text(json.dumps(card), encoding="utf-8")
    status = root / "status"
    status.mkdir(exist_ok=True)
    (status / "annika.md").write_text(f"## annika status, {at(0)}\n\n{SECRET_STATUS}\n", encoding="utf-8")
