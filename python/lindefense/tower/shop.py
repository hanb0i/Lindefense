"""Pricing helpers: purchase, upgrade, ability unlock, sell refunds (70%) and shop availability."""
import math

from lindefense.tower import catalog

SELL_FRACTION = 0.70


def price_of(type_, game=None) -> int:
    base = catalog.get(type_).base_cost
    return base if game is None else game.get_variance().tower_price(base)


def upgrade_cost(t, game=None) -> int:
    u = t.next_upgrade()
    if game is None:
        return 0 if u is None else u.cost
    return upgrade_price(game, u)


def upgrade_price(game, u) -> int:
    return 0 if u is None else game.get_variance().upgrade_price(u.cost)


def ability_unlock_cost(game) -> int:
    return game.get_variance().ability_unlock_price(catalog.ABILITY_UNLOCK_COST)


def sell_fraction(game) -> float:
    return game.get_variance().sell_fraction(SELL_FRACTION)


def sell_value(t, game=None) -> int:
    if game is None:
        return int(math.floor(t.get_invested_cost() * SELL_FRACTION))
    paid = max(0, t.get_invested_cost() - game.get_variance().unpaid_on(t))
    return int(math.floor(paid * sell_fraction(game)))


def unlock_price_of(type_) -> int:
    return catalog.get(type_).unlock_cost


def unavailable_reason(game, type_):
    hero = game.get_tower_manager().hero_problem(type_)
    if hero is not None:
        return hero
    if game.get_cash() < price_of(type_, game):
        return "Not enough cash"
    return None
