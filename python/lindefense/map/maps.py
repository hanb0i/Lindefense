"""The seven campaign maps and the map catalog."""
import math

from lindefense.javacompat import fmt0
from lindefense.map.game_map import GameMap, Obstacle, Decoration, WIDTH
from lindefense.map.path import Path, rounded
from lindefense.sim.vec import Vec


def _faction():
    from lindefense.tower.tower_type import Faction
    return Faction


# ====================================================================== Map 1
class SiliconCircuit(GameMap):
    """The Silicon Circuit (Beginner): capacitor pads and trace short-circuits."""
    PAD_CHARGE_TIME = 20.0
    PAD_CASH = 25.0
    PAD_BOOST_RADIUS = 110.0
    SHORT_INTERVAL = 25.0

    def __init__(self):
        super().__init__("The Silicon Circuit", "Beginner",
                         "A dual-lane printed circuit board. Gold traces carry two independent streams of data.")
        self.routes.append(Path("Trace A", 0, 230, 230, 230, 230, 120, 540, 120, 540, 380, 830, 380, 830, 200, 1200, 200))
        self.routes.append(Path("Trace B", 0, 650, 330, 650, 330, 800, 650, 800, 650, 580, 930, 580, 930, 730, 1200, 730))
        self._pads = [Vec(150, 440), Vec(430, 520), Vec(1040, 440)]
        self._pad_charge = [0.0, 0.0, 0.0]
        self._short_timer = self.SHORT_INTERVAL
        self._shorted_lane = -1
        self._short_remaining = 0.0
        self._banner = None
        self._banner_time = 0.0
        self.obstacles.append(Obstacle(900, 30, 170, 60, False, "CPU"))
        self.obstacles.append(Obstacle(60, 790, 150, 80, False, "RAM"))
        self.obstacles.append(Obstacle(1000, 810, 160, 60, False, "I/O"))
        for o in self.obstacles:
            self.add_decoration(Decoration.rect(o.x, o.y, o.w, o.h, 0x1f2a33))
            self.add_decoration(Decoration.frame(o.x, o.y, o.w, o.h, 0x8a929a))
            self.add_decoration(Decoration.label(o.x + 10, o.y + o.h / 2 + 5, o.label, 0xc0c8d0))
        for p in self._pads:
            self.add_decoration(Decoration.oval(p.x - 42, p.y - 42, 84, 84, 0x2d4a3e, True))
            self.add_decoration(Decoration.oval(p.x - 42, p.y - 42, 84, 84, 0x7fd8a8, False))
            self.add_decoration(Decoration.label(p.x - 36, p.y + 58, "Capacitor Pad", 0x7fd8a8))
        for i in range(40):
            x = 40 + (i * 173) % 1120
            y = 60 + (i * 389) % 780
            self.add_decoration(Decoration.oval(x, y, 6, 6, 0x3b4b3b, True))

    def get_background_rgb(self):
        return 0x11331f

    def get_track_rgb(self):
        return 0xd4a62a

    def get_mechanic_summary(self):
        return "Capacitor Pads charge Support towers (cash + speed). Trace Short-Circuits periodically zap one lane and boost towers along it."

    def get_pads(self):
        return self._pads

    def get_pad_charge(self, i):
        return self._pad_charge[i] / self.PAD_CHARGE_TIME

    def get_shorted_lane(self):
        return self._shorted_lane if self._short_remaining > 0 else -1

    def reset(self):
        self._pad_charge = [0.0, 0.0, 0.0]
        self._short_timer = self.SHORT_INTERVAL
        self._shorted_lane = -1
        self._short_remaining = 0.0
        self._banner = None

    def pad_index_for(self, t):
        for i, p in enumerate(self._pads):
            if p.within_dist(t.get_position(), 44):
                return i
        return -1

    def update(self, game, dt):
        Faction = _faction()
        self._banner_time -= dt
        if self._banner_time <= 0:
            self._banner = None
        towers = game.get_tower_manager().get_towers()
        for i, pad in enumerate(self._pads):
            self._pad_charge[i] = min(self.PAD_CHARGE_TIME, self._pad_charge[i] + dt)
            if self._pad_charge[i] >= self.PAD_CHARGE_TIME:
                occupant = None
                for t in towers:
                    if (not t.is_temporary() and pad.within_dist(t.get_position(), 44)
                            and t.get_type().faction in (Faction.SUPPORT, Faction.HERO)):
                        occupant = t
                        break
                if occupant is not None:
                    self._pad_charge[i] = 0.0
                    game.add_cash(self.PAD_CASH, pad)
                    for t in towers:
                        if t.get_position().within_dist(pad, self.PAD_BOOST_RADIUS):
                            t.add_buff(1.4, 1.0, 1.0, 6)
                    game.emit_text(pad, "Capacitor discharge!", 0x7fd8a8)
        if self._short_remaining > 0:
            self._short_remaining -= dt
        else:
            self._short_timer -= dt
            if self._short_timer <= 0:
                self._short_timer = self.SHORT_INTERVAL
                self._shorted_lane = game.get_rng().next_int(len(self.routes))
                self._short_remaining = 2.0
                lane = self.routes[self._shorted_lane]
                for e in list(game.get_enemy_manager().get_enemies()):
                    if e.get_route() is lane and not e.is_boss():
                        game.get_combat().apply_map_damage(e, 2)
                for t in towers:
                    if lane.distance_to_point(t.get_position()) <= 60:
                        t.add_buff(1.0, 1.3, 1.0, 8)
                self._banner = "Short-circuit on " + lane.get_name() + "!"
                self._banner_time = 3.0

    def get_event_text(self):
        return self._banner


# ====================================================================== Map 2
class LegacyMonolith(GameMap):
    """The Legacy Monolith (Intermediate): line-of-sight chassis and thermal venting floors."""
    FLOORS = ((50, 215), (215, 425), (425, 635), (635, 850))

    def __init__(self):
        super().__init__("The Legacy Monolith", "Intermediate",
                         "A towering server rack. Data spirals down four floors past rows of humming chassis.")
        self.routes.append(Path("Rack Spiral", 80, 0, 80, 110, 1120, 110, 1120, 320, 80, 320, 80, 530, 1120, 530, 1120, 740, 0, 740))
        self._vented_floor = -1
        self._heat_timer = 0.0
        self._banner = None
        self._banner_time = 0.0
        chassis = ((300, 175), (700, 175), (300, 385), (700, 385), (300, 595), (700, 595))
        for n, c in enumerate(chassis, start=1):
            self.obstacles.append(Obstacle(c[0], c[1], 200, 80, True, "SRV-0" + str(n)))
        for o in self.obstacles:
            self.add_decoration(Decoration.rect(o.x, o.y, o.w, o.h, 0x2a2f3a))
            self.add_decoration(Decoration.frame(o.x, o.y, o.w, o.h, 0x6f7a8c))
            for i in range(4):
                self.add_decoration(Decoration.rect(o.x + 12, o.y + 10 + i * 17, o.w - 24, 8, 0x3b4454))
            self.add_decoration(Decoration.oval(o.x + o.w - 22, o.y + 8, 8, 8, 0x5ce07a, True))
            self.add_decoration(Decoration.label(o.x + 12, o.y + o.h - 6, o.label, 0xa6b0c4))
        for f in self.FLOORS:
            self.add_decoration(Decoration.line(0, f[0], WIDTH, f[0], 0x3a4150))
        for i, y in enumerate((70, 280, 490, 700)):
            self.add_decoration(Decoration.label(1130, y, "FLOOR " + str(i + 1), 0x6f7a8c))

    def get_background_rgb(self):
        return 0x161a22

    def get_track_rgb(self):
        return 0x4f6f8f

    def get_mechanic_summary(self):
        return "Server chassis block line of sight. Every 10 waves a random floor vents heat, hurting enemies and slowing towers there."

    def floor_of(self, p):
        for i, f in enumerate(self.FLOORS):
            if f[0] <= p.y < f[1]:
                return i
        return -1

    def get_vented_floor(self):
        return self._vented_floor

    def get_floors(self):
        return self.FLOORS

    def reset(self):
        self._vented_floor = -1
        self._banner = None

    def on_wave_start(self, game, wave):
        if wave % 10 == 0:
            self._vented_floor = game.get_rng().next_int(len(self.FLOORS))
            self._banner = "Thermal Overload Venting on Floor " + str(self._vented_floor + 1) + "!"
            self._banner_time = 5.0
        else:
            self._vented_floor = -1

    def update(self, game, dt):
        self._banner_time -= dt
        if self._banner_time <= 0:
            self._banner = None
        if self._vented_floor < 0:
            return
        self._heat_timer += dt
        if self._heat_timer >= 2.0:
            self._heat_timer = 0.0
            for e in list(game.get_enemy_manager().get_enemies()):
                if self.floor_of(e.get_position()) == self._vented_floor:
                    game.get_combat().apply_map_damage(e, 1)

    def enemy_speed_multiplier(self, e):
        return 0.9 if self._vented_floor >= 0 and self.floor_of(e.get_position()) == self._vented_floor else 1.0

    def tower_rate_multiplier(self, game, t):
        return 0.75 if self._vented_floor >= 0 and self.floor_of(t.get_position()) == self._vented_floor else 1.0

    def get_event_text(self):
        if self._banner is not None:
            return self._banner
        return "Floor " + str(self._vented_floor + 1) + " is venting heat" if self._vented_floor >= 0 else None


# ====================================================================== Map 3
class BridgeNode:
    def __init__(self, pos, route_index, distance):
        self.pos, self.route_index, self.distance = pos, route_index, distance


class HallucinationCanyon(GameMap):
    """The Hallucination Canyon (Advanced): attention drift teleports and noise storms."""
    STORM_INTERVAL = 32.0
    STORM_DURATION = 9.0
    SPECIALIST_RADIUS = 140.0
    DRIFT_CHANCE = 0.25

    def __init__(self):
        super().__init__("The Hallucination Canyon", "Advanced",
                         "A fractured neural canyon. Attention drifts at the hub; noise storms cloud every sensor.")
        self._center = Vec(600, 450)
        self._nodes = []
        self._storm_timer = self.STORM_INTERVAL
        self._storm_remaining = 0.0
        self.routes.append(Path("Dendrite Descent",
                                600, 0, 600, 140, 440, 140, 440, 260, 600, 260, 600, 450, 600, 640, 760, 640, 760, 780, 600, 780, 600, 900))
        self.routes.append(Path("Axon Crossing",
                                0, 450, 160, 450, 160, 320, 380, 320, 380, 450, 600, 450, 820, 450, 820, 580, 1040, 580, 1040, 450, 1200, 450))
        self._add_node(600, 260, 0)
        self._add_node(600, 640, 0)
        self._add_node(380, 450, 1)
        self._add_node(820, 450, 1)
        gaps = ((60, 60, 260, 180), (880, 60, 260, 220), (60, 660, 300, 200), (900, 700, 240, 160), (60, 300, 60, 120), (1100, 240, 80, 160))
        for g in gaps:
            self.obstacles.append(Obstacle(g[0], g[1], g[2], g[3], False, "Gap"))
            self.add_decoration(Decoration.rect(g[0], g[1], g[2], g[3], 0x0e0a1a))
            self.add_decoration(Decoration.frame(g[0], g[1], g[2], g[3], 0x3f2d6b))
        for n in self._nodes:
            self.add_decoration(Decoration.oval(n.pos.x - 26, n.pos.y - 26, 52, 52, 0x3f2d6b, True))
            self.add_decoration(Decoration.oval(n.pos.x - 26, n.pos.y - 26, 52, 52, 0xb48cff, False))
        c = self._center
        self.add_decoration(Decoration.oval(c.x - 40, c.y - 40, 80, 80, 0x5a3fa0, True))
        self.add_decoration(Decoration.oval(c.x - 40, c.y - 40, 80, 80, 0xe0c8ff, False))
        self.add_decoration(Decoration.label(c.x - 48, c.y - 48, "Attention Hub", 0xe0c8ff))
        for i in range(60):
            x = 30 + (i * 211) % 1140
            y = 30 + (i * 157) % 840
            self.add_decoration(Decoration.oval(x, y, 4, 4, 0x4a3a7a, True))

    def _add_node(self, x, y, route):
        p = Vec(x, y)
        self._nodes.append(BridgeNode(p, route, self.routes[route].nearest_distance_along(p)))

    def get_background_rgb(self):
        return 0x1b1430

    def get_track_rgb(self):
        return 0x8f7fcf

    def get_mechanic_summary(self):
        return "Attention Drift: 25% of enemies crossing the hub teleport to another bridge node. Noise Storms halve tower range unless a Logic Specialist is nearby."

    def is_storm_active(self):
        return self._storm_remaining > 0

    def get_storm_remaining(self):
        return self._storm_remaining

    def get_nodes(self):
        return self._nodes

    def get_center(self):
        return self._center

    def reset(self):
        self._storm_timer = self.STORM_INTERVAL
        self._storm_remaining = 0.0

    def update(self, game, dt):
        if self._storm_remaining > 0:
            self._storm_remaining -= dt
        else:
            self._storm_timer -= dt
            if self._storm_timer <= 0:
                self._storm_timer = self.STORM_INTERVAL
                self._storm_remaining = self.STORM_DURATION
                game.emit_text(self._center, "Noise Storm!", 0xff8cf0)

    def on_enemy_moved(self, game, e):
        if e.has_drifted() or e.is_stored():
            return
        if e.get_position().within_dist(self._center, 18):
            e.set_drifted(True)
            if game.get_rng().chance(self.DRIFT_CHANCE):
                n = self._nodes[game.get_rng().next_int(len(self._nodes))]
                e.teleport_to(self.routes[n.route_index], n.route_index, n.distance)
                game.emit_teleport(e.get_position())

    def tower_range_multiplier(self, game, t):
        if self._storm_remaining <= 0:
            return 1.0
        if t is None:
            return 0.5
        Faction = _faction()
        for o in game.get_tower_manager().get_towers():
            if o.get_type().faction is Faction.MILITARY and o.get_position().dist(t.get_position()) <= self.SPECIALIST_RADIUS:
                return 1.0
        return 0.5

    def get_event_text(self):
        return "Noise Storm: tower range halved (" + fmt0(self._storm_remaining) + "s)" if self._storm_remaining > 0 else None


# ====================================================================== Map 4
class SingularityCore(GameMap):
    """The Singularity Core (Expert): gravitational pull and the wave-50 Event Horizon Collapse."""
    ARENA_RADIUS = 430.0
    COLLAPSE_DELAY = 15.0
    COLLAPSE_WAVE = 50

    def __init__(self):
        super().__init__("The Singularity Core", "Expert",
                         "Four portals feed a central vortex. Gravity accelerates everything that falls inward.")
        self._center = Vec(600, 450)
        self._collapse_pending = False
        self._collapse_timer = 0.0
        self._collapsed = False
        self._banner = None
        self._banner_time = 0.0
        names = ("North Portal", "East Portal", "South Portal", "West Portal")
        for i in range(4):
            self.routes.append(Path(names[i], self._spiral(-90 + 90 * i)))
        c, R = self._center, self.ARENA_RADIUS
        self.add_decoration(Decoration.oval(c.x - R, c.y - R, R * 2, R * 2, 0x1a1030, True))
        self.add_decoration(Decoration.oval(c.x - R, c.y - R, R * 2, R * 2, 0x6a4fcf, False))
        r = 360.0
        while r > 60:
            self.add_decoration(Decoration.oval(c.x - r, c.y - r, r * 2, r * 2, 0x2c2050, False))
            r -= 110
        self.add_decoration(Decoration.oval(c.x - 48, c.y - 48, 96, 96, 0x000000, True))
        self.add_decoration(Decoration.oval(c.x - 48, c.y - 48, 96, 96, 0xb090ff, False))
        self.add_decoration(Decoration.oval(c.x - 30, c.y - 30, 60, 60, 0x40208a, False))
        for p in self.routes:
            s = p.get_start()
            self.add_decoration(Decoration.oval(s.x - 24, s.y - 24, 48, 48, 0x4020a0, True))
            self.add_decoration(Decoration.oval(s.x - 24, s.y - 24, 48, 48, 0xc0a0ff, False))

    def _spiral(self, start_deg):
        pts = []
        a = math.radians(start_deg)
        pts.append(self._polar(self.ARENA_RADIUS, a))
        pts.append(self._polar(360, a))
        ang = start_deg
        for k in range(1, 11):
            pts.append(self._polar(360, math.radians(ang + k * 10)))
        ang += 100
        pts.append(self._polar(250, math.radians(ang)))
        for k in range(1, 11):
            pts.append(self._polar(250, math.radians(ang + k * 10)))
        ang += 100
        pts.append(self._polar(140, math.radians(ang)))
        for k in range(1, 9):
            pts.append(self._polar(140, math.radians(ang + k * 10)))
        pts.append(self._center)
        return pts

    def _polar(self, r, ang):
        return Vec(self._center.x + r * math.cos(ang), self._center.y + r * math.sin(ang))

    def get_background_rgb(self):
        return 0x07050e

    def get_track_rgb(self):
        return 0x7a5fe0

    def get_mechanic_summary(self):
        return "Gravitational Pull speeds enemies up near the core. Event Horizon Collapse at Wave 50 resets ability cooldowns and scatters enemies across all portals."

    def get_center(self):
        return self._center

    def has_collapsed(self):
        return self._collapsed

    def is_inside_arena(self, p):
        r = p.dist(self._center)
        return 70 <= r <= self.ARENA_RADIUS - 20

    def reset(self):
        self._collapse_pending = False
        self._collapsed = False
        self._banner = None

    def on_wave_start(self, game, wave):
        if wave == self.COLLAPSE_WAVE:
            self._collapse_pending = True
            self._collapse_timer = self.COLLAPSE_DELAY
            self._banner = "Warning: the Event Horizon is destabilising..."
            self._banner_time = 6.0

    def update(self, game, dt):
        self._banner_time -= dt
        if self._banner_time <= 0:
            self._banner = None
        if self._collapse_pending:
            self._collapse_timer -= dt
            if self._collapse_timer <= 0:
                self._collapse_pending = False
                self._collapsed = True
                self.trigger_collapse(game)

    def trigger_collapse(self, game):
        for t in game.get_tower_manager().get_towers():
            t.reset_ability_cooldown()
        for e in list(game.get_enemy_manager().get_enemies()):
            if e.is_stored():
                continue
            frac = e.get_distance() / e.get_route().get_total_length()
            idx = game.get_rng().next_int(len(self.routes))
            np_ = self.routes[idx]
            e.teleport_to(np_, idx, frac * np_.get_total_length())
            game.emit_teleport(e.get_position())
        self._banner = "EVENT HORIZON COLLAPSE! Cooldowns reset, enemies scattered."
        self._banner_time = 6.0
        game.emit_text(self._center, "EVENT HORIZON COLLAPSE", 0xd0b0ff)

    def enemy_speed_multiplier(self, e):
        r = e.get_position().dist(self._center)
        return 1.0 + 0.6 * max(0.0, 1 - r / self.ARENA_RADIUS)

    def get_event_text(self):
        return self._banner


# ====================================================================== Map 5
class SiliconValley(GameMap):
    """Silicon Valley (Intermediate): one long winding road, no special mechanics."""
    SKYBRIDGES = ((340, 262, 80, 26), (1030, 395, 80, 26), (418, 650, 182, 22))

    def __init__(self):
        super().__init__("Silicon Valley", "Intermediate",
                         "The Innovation District. A winding campus road snakes between AI labs, glass headquarters and humming server farms.")
        self.routes.append(Path("Innovation Drive", rounded(70,
                                0, 150, 380, 150, 380, 400, 170, 400, 170, 760, 560, 760, 560, 520, 800, 520,
                                800, 130, 1070, 130, 1070, 760, 1200, 760)))
        for args in ((30, 20, 180, 90, "DATA CENTER"), (30, 210, 170, 120, "AI RESEARCH LAB"), (20, 470, 110, 250, "SERVER FARM"),
                     (250, 470, 150, 130, "NEXUS HQ"), (450, 30, 200, 110, "GLASS HQ"), (600, 300, 140, 110, "ROBOTICS LAB"),
                     (860, 560, 150, 160, "SERVER FARM"), (1110, 220, 75, 260, "AV DEPOT"), (880, 20, 170, 70, "HOLO BOARD"),
                     (600, 610, 170, 100, "CHARGING HUB")):
            self.obstacles.append(Obstacle(args[0], args[1], args[2], args[3], False, args[4]))
        for o in self.obstacles:
            self.add_decoration(Decoration.rect(o.x, o.y, o.w, o.h, 0x1c2a3c))
            self.add_decoration(Decoration.frame(o.x, o.y, o.w, o.h, 0x5fd4ff))

    def get_skybridges(self):
        return self.SKYBRIDGES

    def get_background_rgb(self):
        return 0x0b1424

    def get_track_rgb(self):
        return 0x3fb8ff

    def get_mechanic_summary(self):
        return "No special mechanics. One long winding road through the tech campus; buildings block placement, and the rounded bends reward towers that cover two stretches at once."


# ====================================================================== Map 6
class NeuralNetwork(GameMap):
    """The Neural Network (Advanced): six branching routes into one output neuron."""
    IN_A, IN_B = Vec(0, 200), Vec(0, 700)
    J1, J2 = Vec(240, 200), Vec(240, 700)
    H1, H2, H3 = Vec(480, 110), Vec(480, 450), Vec(480, 790)
    H4, H5 = Vec(780, 280), Vec(780, 620)
    OUT, EXIT = Vec(990, 450), Vec(1200, 450)

    def __init__(self):
        super().__init__("The Neural Network", "Advanced",
                         "Inside the machine. Synapse pathways branch and merge through glowing neurons; six routes converge on a single output.")
        C = NeuralNetwork
        self._route("Synapse A-1", C.IN_A, C.J1, C.H1, C.H4)
        self._route("Synapse A-2", C.IN_A, C.J1, C.H2, C.H4)
        self._route("Synapse A-3", C.IN_A, C.J1, C.H2, C.H5)
        self._route("Synapse B-1", C.IN_B, C.J2, C.H2, C.H4)
        self._route("Synapse B-2", C.IN_B, C.J2, C.H2, C.H5)
        self._route("Synapse B-3", C.IN_B, C.J2, C.H3, C.H5)
        self._neurons = (C.J1, C.J2, C.H1, C.H2, C.H3, C.H4, C.H5, C.OUT)
        for v in self._neurons:
            self.add_decoration(Decoration.oval(v.x - 34, v.y - 34, 68, 68, 0x3a1460, True))
            self.add_decoration(Decoration.oval(v.x - 34, v.y - 34, 68, 68, 0xff4bd8, False))

    def _route(self, name, *via):
        xy = []
        for v in via:
            xy += [v.x, v.y]
        xy += [self.OUT.x, self.OUT.y, self.EXIT.x, self.EXIT.y]
        self.routes.append(Path(name, rounded(28, *xy)))

    def get_neurons(self):
        return self._neurons

    def get_background_rgb(self):
        return 0x060818

    def get_track_rgb(self):
        return 0x38e8ff

    def get_mechanic_summary(self):
        return "No special mechanics. Two inputs branch through the hidden layers into six routes that merge at the output neuron: defend several branches or hold the output."


# ====================================================================== Map 7
class Hazard:
    def __init__(self, name, kind, rgb, frm, to):
        self.name, self.kind, self.rgb, self.frm, self.to = name, kind, rgb, frm, to

    def covers(self, d):
        return self.frm <= d <= self.to

    @property
    def from_(self):
        """Java's field name (`from` is a Python keyword); the ported UI reads it as from_."""
        return self.frm


class AbandonedDataCenter(GameMap):
    """Abandoned Data Center (Beginner): malfunctioning hazard sections slow enemies."""
    HAZARD_INTERVAL = 16.0
    HAZARD_WARNING = 2.0
    HAZARD_DURATION = 7.0
    HAZARD_SLOW = 0.45

    def __init__(self):
        super().__init__("Abandoned Data Center", "Beginner",
                         "The Server Graveyard. A long path twists through dead server aisles, past failing cooling plants and sparking cables.")
        self._hazards = []
        self._active = self._warned = self._last = -1
        self._timer = self.HAZARD_INTERVAL - self.HAZARD_WARNING
        self._remaining = 0.0
        self._banner = None
        self._banner_time = 0.0
        p = Path("Maintenance Route",
                 0, 90, 130, 90, 130, 780, 290, 780, 290, 160, 450, 160, 450, 700, 750, 700,
                 750, 160, 910, 160, 910, 780, 1070, 780, 1070, 90, 1200, 90)
        self.routes.append(p)
        self._hazard(p, "Aisle 2 Live Cables", "SPARKS", 0xffd23b, Vec(290, 640), Vec(290, 330))
        self._hazard(p, "Coolant Leak", "COOLANT", 0x5fe8ff, Vec(480, 700), Vec(720, 700))
        self._hazard(p, "Aisle 5 Fan Failure", "TURBINE", 0x9cff6a, Vec(910, 330), Vec(910, 640))
        self._hazard(p, "Exit Vent Blowback", "VENT", 0xff7a3b, Vec(1070, 640), Vec(1070, 330))
        for args in ((500, 300, 200, 240, "COOLING PLANT"), (180, 260, 60, 150, "RACK"), (340, 520, 60, 150, "RACK"),
                     (800, 260, 60, 150, "RACK"), (960, 520, 60, 150, "RACK"), (20, 220, 66, 200, "RACK"),
                     (1114, 470, 66, 200, "RACK"), (520, 20, 160, 70, "UPS BANK")):
            self.obstacles.append(Obstacle(args[0], args[1], args[2], args[3], False, args[4]))
        for o in self.obstacles:
            self.add_decoration(Decoration.rect(o.x, o.y, o.w, o.h, 0x1b1f24))
            self.add_decoration(Decoration.frame(o.x, o.y, o.w, o.h, 0x6a6f78))

    def _hazard(self, p, name, kind, rgb, a, b):
        da, db = p.nearest_distance_along(a), p.nearest_distance_along(b)
        self._hazards.append(Hazard(name, kind, rgb, min(da, db), max(da, db)))

    def get_hazards(self):
        return self._hazards

    def get_active_hazard(self):
        return self._active if self._remaining > 0 else -1

    def get_warned_hazard(self):
        return self._warned

    def get_hazard_remaining(self):
        return max(0.0, self._remaining)

    def get_background_rgb(self):
        return 0x0b0d10

    def get_track_rgb(self):
        return 0x9aa4b0

    def get_mechanic_summary(self):
        return "Malfunctioning Infrastructure: every 16 s one of four marked track sections sparks, leaks coolant or blasts air, slowing enemies there by 45% for 7 s."

    def reset(self):
        self._active = self._warned = self._last = -1
        self._remaining = 0.0
        self._timer = self.HAZARD_INTERVAL - self.HAZARD_WARNING
        self._banner = None

    def update(self, game, dt):
        self._banner_time -= dt
        if self._banner_time <= 0:
            self._banner = None
        if self._remaining > 0:
            self._remaining -= dt
            if self._remaining <= 0:
                self._active = -1
        self._timer -= dt
        if self._warned < 0 and self._timer <= 0:
            if self._last < 0:
                pick = game.get_rng().next_int(len(self._hazards))
            else:
                pick = game.get_rng().next_int(len(self._hazards) - 1)
                if pick >= self._last:
                    pick += 1
            self._warned = pick
            self._timer = self.HAZARD_WARNING
            self._banner = "Warning: " + self._hazards[pick].name + " is failing..."
            self._banner_time = self.HAZARD_WARNING
        elif self._warned >= 0 and self._timer <= 0:
            self._active = self._warned
            self._last = self._warned
            self._warned = -1
            self._remaining = self.HAZARD_DURATION
            self._timer = self.HAZARD_INTERVAL - self.HAZARD_WARNING
            h = self._hazards[self._active]
            mid = self.routes[0].position_at((h.frm + h.to) / 2)
            game.emit_text(mid, h.kind + "!", h.rgb)
            self._banner = None

    def enemy_speed_multiplier(self, e):
        if self._remaining <= 0 or self._active < 0 or e.is_stored() or e.get_route() is not self.routes[0]:
            return 1.0
        if not self._hazards[self._active].covers(e.get_distance()):
            return 1.0
        return 1.0 - (self.HAZARD_SLOW / 3 if e.is_boss() else self.HAZARD_SLOW)

    def get_event_text(self):
        if self._banner is not None:
            return self._banner
        a = self.get_active_hazard()
        return (self._hazards[a].name + ": enemies slowed (" + fmt0(self._remaining) + "s)") if a >= 0 else None


# ====================================================================== catalog
MAP_COUNT = 7
_FACTORIES = (SiliconCircuit, LegacyMonolith, HallucinationCanyon, SingularityCore, SiliconValley, NeuralNetwork, AbandonedDataCenter)


def create(index: int) -> GameMap:
    if not 0 <= index < MAP_COUNT:
        raise ValueError("No map " + str(index))
    return _FACTORIES[index]()


def index_of(m: GameMap) -> int:
    for i in range(MAP_COUNT):
        if create(i).get_name() == m.get_name():
            return i
    return -1


def create_all():
    return [create(i) for i in range(MAP_COUNT)]
