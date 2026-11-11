"""The frame loop's error handling: an exception in one input / frame / paint step is reported and the game keeps
running (Java's event-dispatch thread printed the trace and carried on), instead of closing the window."""
from lindefense.app import LindefenseApp


def test_handler_exceptions_do_not_close_the_game(check, capsys):
    app = LindefenseApp.__new__(LindefenseApp)   # no window needed for the guard itself
    app._errors = {}
    calls = []

    def boom(dt):
        calls.append(dt)
        raise RuntimeError("boom")

    for _ in range(12):
        app._guarded("frame", boom, 0.016)          # must not raise
    err = capsys.readouterr().err
    check(len(calls) == 12, "every step still runs after an error (%d)" % len(calls))
    check(err.count("RuntimeError: boom") == 1, "the trace is printed once, not every frame")
    check("again (10 times so far)" in err, "repeats are counted")

    ok = []
    app._guarded("paint", lambda: ok.append(1))
    check(ok == [1], "a step that doesn't fail just runs")
