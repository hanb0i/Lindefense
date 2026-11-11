"""pytest harness for the headless suite.

Tests take a ``check`` fixture and call ``check(cond, message)`` for every assertion, exactly like the Java suite's
TestKit.check: a failing check is recorded and the test keeps going, and the test fails at the end listing every
failed message. The total number of checks is printed in the terminal summary.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# tests never touch the player's real save folder (settings, Hero Store, records): everything goes to a temp folder
os.environ["LINDEFENSE_PREFS_DIR"] = tempfile.mkdtemp(prefix="lindefense-test-prefs-")
os.environ.setdefault("LINDEFENSE_NOSOUND", "1")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

_TOTAL = {"passed": 0, "failed": 0}


class Checker:
    def __init__(self):
        self.passed = 0
        self.failures = []

    def __call__(self, cond, msg=""):
        if cond:
            self.passed += 1
            _TOTAL["passed"] += 1
        else:
            self.failures.append(str(msg))
            _TOTAL["failed"] += 1
        return bool(cond)


@pytest.fixture
def check():
    return Checker()


@pytest.hookimpl(hookwrapper=True)
def pytest_pyfunc_call(pyfuncitem):
    outcome = yield
    chk = pyfuncitem.funcargs.get("check")
    if chk is not None and chk.failures and outcome.excinfo is None:
        shown = chk.failures[:40]
        more = "" if len(chk.failures) <= 40 else "\n  ... and %d more" % (len(chk.failures) - 40)
        outcome.force_exception(AssertionError(
            "%d failed check(s):\n  %s%s" % (len(chk.failures), "\n  ".join(shown), more)))


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line("checks: %d passed, %d failed" % (_TOTAL["passed"], _TOTAL["failed"]))
