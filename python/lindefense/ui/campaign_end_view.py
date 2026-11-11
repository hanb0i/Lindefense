"""The end of a campaign level, over the playfield: LEVEL COMPLETE with the stars earned and a NEW TOWER UNLOCKED card
for each reward (the tower's art, name and role), then NEXT LEVEL / CAMPAIGN / RETRY; or DEFEAT with RETRY / CAMPAIGN.
The finale says CAMPAIGN COMPLETE (after the epilogue) and offers CAMPAIGN / RETRY / MAIN MENU.

Below them, the story (ui/story_view.py): the level's outcome and the new towers' first lines, or Mr. Lindemann's retry
nudge after a defeat.

What the level changed comes from the run session's campaign Outcome (sim/campaign.py: stars, first clear, unlocks);
a screen without a session (tests, snapshots) shows what a first clear would give. Drawn flat with the shared helpers
(UIButton, Cyber, Ui)."""
from lindefense.sim import campaign
from lindefense.sim.campaign import CampaignProgress
from lindefense.tower import catalog
from lindefense.ui import story_view as StoryView
from lindefense.ui.cyber import Cyber
from lindefense.ui.jawt import Color, Font
from lindefense.ui.ui import Ui
from lindefense.ui.ui_button import UIButton

PANEL_W = 780.0


def outcome_for(screen):
    """The level's Outcome: the session's (recorded when the level ended), else a preview against empty progress."""
    s = screen.session
    out = getattr(s, "campaign_outcome", None) if s is not None else None
    if out is None:
        out = CampaignProgress.in_memory().record_game(screen.game)
    return out


def _flat(x, y, w, h, cut, fill, border, lw=1.2):
    from lindefense.ui.campaign_screen import flat
    return flat(x, y, w, h, cut, fill, border, lw)


def _centered(into, text, cx, y, f, col):
    lbl = Ui.label(text, 0, y, f, col)
    lbl.set_location(cx - lbl.get_width() / 2, y)
    into.add(lbl)
    return lbl


def _app_call(screen, name, *args):
    app = screen.app
    fn = getattr(app, name, None) if app is not None else None
    if fn is not None:
        fn(*args)


def achievements_line(screen):
    """'Achievement unlocked: Fully Trained' (the run report's unlocks; a level's end shows no records line), or ''."""
    rep = screen.get_run_report() if hasattr(screen, "get_run_report") else None
    # the ones only checked at the end first (live ones, e.g. boss kills, were already toasted during play)
    names = [a.title for a in sorted(rep.unlocked if rep is not None else (), key=lambda a: a.live)]
    if not names:
        return ""
    head = "Achievement unlocked: " if len(names) == 1 else "%d achievements unlocked: " % len(names)
    more = ("  +%d more" % (len(names) - 3)) if len(names) > 3 else ""
    return head + "  \u00b7  ".join(names[:3]) + more


def buttons_for(screen, won, out):
    """[(label, accent, action)] for the panel's button row."""
    c = screen.game.get_campaign()
    lv = c.level()
    rows = []
    nxt = campaign.level(lv.index + 1)
    if won and nxt is not None:
        rows.append(("NEXT LEVEL", Cyber.YELLOW, lambda: _app_call(screen, "show_campaign", nxt.id)))
    if not won:
        rows.append(("RETRY", Cyber.YELLOW, lambda: _app_call(screen, "restart_level")))
    rows.append(("CAMPAIGN", Cyber.CYAN, lambda: _app_call(screen, "show_campaign")))
    if won:
        rows.append(("RETRY", Cyber.MAGENTA, lambda: _app_call(screen, "restart_level")))
    if won and nxt is None:
        rows.append(("MAIN MENU", Cyber.MAGENTA, lambda: _app_call(screen, "show_menu")))
    return rows


def reward_card(into, t, x, y, w, h):
    """NEW TOWER UNLOCKED: the tower's art, name, subtitle and faction."""
    from lindefense.ui.campaign_screen import tower_icon
    d = catalog.get(t)
    acc = Ui.c(t.primary_rgb)
    into.add(_flat(x, y, w, h, 10, Color(9, 15, 32, 240), Cyber.alpha(Cyber.lerp(acc, Cyber.YELLOW, 0.5), 200), 1.4))
    isz = h - 24
    into.add(tower_icon(t, x + 12, y + 12, isz))
    tx = x + isz + 26
    into.add(Ui.label("NEW TOWER UNLOCKED", tx, y + 26, Cyber.body(Font.BOLD, 13), Cyber.YELLOW))
    from lindefense.ui.catalog_screen import CatalogScreen
    nf = CatalogScreen.fit_font(t.display_name.upper(), Cyber.display(Font.BOLD, 28), x + w - 12 - tx, 14)
    into.add(Ui.label(t.display_name.upper(), tx, y + 56, nf, Cyber.TEXT))
    sf = CatalogScreen.fit_font(d.subtitle, Cyber.body(Font.PLAIN, 14), x + w - 12 - tx, 10)
    into.add(Ui.label(d.subtitle, tx, y + 78, sf, Cyber.MUTED))
    into.add(Ui.label("%s  \u00b7  %s" % (t.faction.label, Ui.money(d.base_cost)), tx, y + h - 14,
                      Cyber.body(Font.BOLD, 13), Cyber.alpha(Ui.c(t.faction.rgb), 230)))


def build(screen):
    """Builds the panel into screen.overlay (buttons into screen.overlay_buttons)."""
    from lindefense.sim.game import Game
    from lindefense.ui import run_report_view as RunReportView
    g = screen.game
    c = g.get_campaign()
    lv = c.level()
    st = g.get_state()
    won = st is Game.State.VICTORY
    out = outcome_for(screen) if won else None
    ov = screen.overlay
    ov.add(Ui.rect(Ui.WORLD_X, Ui.WORLD_Y, Ui.WORLD_W, Ui.WORLD_H, Ui.c(0x02040a, 200), Ui.c(0x000000, 0)))
    cx = Ui.WORLD_X + Ui.WORLD_W / 2.0
    cy = Ui.WORLD_Y + Ui.WORLD_H / 2.0
    towers = list(out.towers) if (out is not None and out.first_clear) else []
    extras = []
    if out is not None and out.heroes:
        extras.append("Hero Store open: unlock heroes with match cash, up to 3 per game.")
    if out is not None and out.abilities:
        extras.append("$15,000 abilities: a fully upgraded tower can unlock its overpowered ability.")
    ach = achievements_line(screen)
    card_h = 116.0
    ph = 336.0 if not won else (430.0 + (card_h + 18 if towers else 0) + 24 * len(extras))
    tale, tale_h = StoryView.story_block(StoryView.outcome_lines(lv, won, out), PANEL_W - 64)
    if tale is not None:
        ph += tale_h + 6
    if ach:
        ph += 26
    px, pw = cx - PANEL_W / 2, PANEL_W
    py = cy - ph / 2
    col = Cyber.YELLOW if won else Cyber.RED
    ov.add(_flat(px, py, pw, ph, 20, Color(6, 10, 24, 245), Cyber.alpha(col, 210), 1.8))
    _centered(ov, "Level %d of %d  \u00b7  %s" % (lv.index, len(campaign.LEVELS), lv.title),
              cx, py + 42, Cyber.body(Font.BOLD, 15), Cyber.alpha(Cyber.MAGENTA, 230))
    if won:
        title = "CAMPAIGN COMPLETE" if lv.is_finale() else "LEVEL COMPLETE"
    else:
        title = "DEFEAT"
    _centered(ov, title, cx, py + 104, Cyber.display(Font.BOLD, 60), Cyber.lerp(col, Color.WHITE, 0.25))
    y = py + 132
    if won:
        r = 24.0
        gap = 18.0
        x0 = cx - (3 * 2 * r + 2 * gap) / 2
        for i in range(3):
            ov.add(RunReportView.star(x0 + r + i * (2 * r + gap), y + r + 4, r,
                                      Cyber.YELLOW if i < out.stars else Cyber.alpha(Cyber.DIM, 140)))
        y += 2 * r + 34
        line = "%d / %d integrity left" % (g.get_lives(), g.get_max_lives())
        if out.new_best:
            line += "  \u00b7  New best"
        elif not out.first_clear and out.best > out.stars:
            line += "  \u00b7  Best: %d stars" % out.best
        _centered(ov, line, cx, y, Cyber.body(Font.BOLD, 16), Cyber.TEXT)
        y += 22
    else:
        sub = "Your defenses were breached on wave %d of %d." % (max(1, g.get_wave()), c.wave_count())
        _centered(ov, sub, cx, y + 10, Cyber.body(Font.PLAIN, 17), Cyber.TEXT)
        y += 34
    # stats
    stats = (("Waves cleared", "%d / %d" % (g.get_last_completed_wave(), c.wave_count()), Cyber.CYAN),
             ("Hostiles purged", Cyber.commas(g.get_enemy_manager().get_total_killed()), Cyber.CYAN),
             ("Credits earned", Ui.money(screen.run_summary().cash_earned), Cyber.YELLOW),   # income, as on CLASSIC
             ("Integrity left", str(g.get_lives()), Cyber.RED))
    cw, gap = 166.0, 12.0
    sx = cx - (4 * cw + 3 * gap) / 2
    for i, (lab, val, ac) in enumerate(stats):
        x = sx + i * (cw + gap)
        ov.add(_flat(x, y, cw, 56, 7, Color(8, 14, 32, 235), Cyber.alpha(ac, 150)))
        ov.add(Ui.label(lab, x + 12, y + 19, Cyber.body(Font.BOLD, 12), Cyber.alpha(ac, 210)))
        ov.add(Ui.label(val, x + 12, y + 44, Cyber.mono(Font.BOLD, 19), Cyber.TEXT))
    y += 76
    if won and towers:
        n = len(towers)
        w = (pw - 64 - (n - 1) * 14) / n
        for i, t in enumerate(towers):
            reward_card(ov, t, px + 32 + i * (w + 14), y, w, card_h)
        y += card_h + 18
    elif won and not lv.is_finale():
        _centered(ov, "Reward already unlocked: " + (", ".join(t.display_name for t in lv.reward) or "-"), cx, y + 14,
                  Cyber.body(Font.PLAIN, 15), Cyber.MUTED)
        y += 30
    elif won:
        _centered(ov, "Palantir has fallen. Every tower is yours: try them all in CLASSIC, 100 waves on any map.", cx,
                  y + 14, Cyber.body(Font.PLAIN, 15), Cyber.TEXT)
        y += 30
    for e in extras:
        _centered(ov, e, cx, y + 14, Cyber.body(Font.BOLD, 15), Cyber.alpha(Cyber.CYAN, 235))
        y += 24
    if tale is not None:   # the story: what happened, who joined
        tale.set_location(px + 32, y + (6 if (extras or (won and not towers)) else 0))
        ov.add(tale)
        screen.story_block = tale
        y += tale_h + 6
    if ach:   # the campaign achievements unlock when the level is recorded: say so here (no toast comes after)
        from lindefense.ui.catalog_screen import CatalogScreen
        _centered(ov, ach, cx, y + 14, CatalogScreen.fit_font(ach, Cyber.body(Font.BOLD, 15), pw - 64, 11), Cyber.YELLOW)
        y += 26
    rows = buttons_for(screen, won, out)
    gap = 12.0
    bw = (pw - 64 - gap * (len(rows) - 1)) / len(rows)
    bx = cx - (pw - 64) / 2
    for i, (label, accent, action) in enumerate(rows):
        b = UIButton(bx + i * (bw + gap), py + ph - 76, bw, 50, label, Cyber.display(Font.BOLD, 20), action)
        b.set_accent(accent)
        b.set_primary(i == 0)
        ov.add(b)
        screen.overlay_buttons.append(b)
