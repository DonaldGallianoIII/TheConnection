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
@complexity O(m) over m = 12 messages.
@alloc      the files, removed with the TcRoot.
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


def at(offset):
    """The fixture's time `offset` seconds after BASE, as a message header writes it.

    @interacts  none.
    @deps       datetime; BASE.
    @complexity O(1).
    @alloc      one string, returned.
    """
    return (BASE + datetime.timedelta(seconds=offset)).isoformat(timespec="seconds")


def build(root):
    """Write the fixture mailbox under `root` (a pathlib.Path: a TcRoot's path).

    @interacts  see the module block.
    @deps       json, os; MESSAGES, CARDS, at.
    @complexity O(m) over m messages.
    @alloc      the files.
    """
    mail = root / "mail"
    for name in ("annika", "bertil", "corwin"):
        (mail / f"to-{name}" / "read").mkdir(parents=True, exist_ok=True)
    records = {}
    for spec in MESSAGES:
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
