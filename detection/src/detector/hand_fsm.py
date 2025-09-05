from enum import Enum


class Place(Enum):
    IDLE = "Idle"
    IN_TABLE = "In Table"
    IN_TOPPINGS = "In Toppings"


class State(Enum):
    IDLE = "Idle"
    IN_TOPPINGS = "In Toppings"
    MOVING_TO_TABLE = "Moving to Table"
    TOUCHING_PIZZA = "Touching Pizza"


class GlobalFSM:
    def __init__(self, cfg):
        self.cfg = cfg
        self.state = State.IDLE
        self.violation_seen = False
        self.scooper_seen = 0
        self.transition_timer = 0
        self.move_timer = 0
        self.scooper_timer = 0
        self.toppings_timer = 0

    def update(self, place, touched_pizzas, scoopers):
        self.violation_seen = False

        def pizza_has_scooper(pizza_bbox):
            for s in scoopers:
                if self._intersect(pizza_bbox, s["bbox"]):
                    return True
            return False

        # Transitions
        if place == Place.IN_TOPPINGS:
            self.state = State.IN_TOPPINGS

        if self.state == State.IN_TOPPINGS:
            if place == Place.IN_TABLE:
                self.transition_timer += 1
                if self.transition_timer > self.cfg["thresholds"]["transition_grace"]:
                    # left toppings and in table
                    if self.toppings_timer >= self.cfg["thresholds"]["toppings_grace"]:
                        self.state = State.MOVING_TO_TABLE
                        self.move_timer = self.cfg["thresholds"]["move_grace"]
                    else:
                        # brief touch of toppings then table — treat as Idle
                        self.state = State.IDLE
                    self.toppings_timer = 0
                    self.transition_timer = 0
            else:
                # increment how long we've been in toppings
                self.toppings_timer += 1

        elif self.state == State.MOVING_TO_TABLE:
            if touched_pizzas:
                self.transition_timer += 1
                if self.transition_timer > self.cfg["thresholds"]["transition_grace"]:
                    # start scooper grace window
                    self.state = State.TOUCHING_PIZZA
                    self.scooper_timer = self.cfg["thresholds"]["scooper_grace"]
                    self.transition_timer = 0
            else:
                self.move_timer -= 1
                if self.move_timer <= 0:
                    self.state = State.IDLE

        elif self.state == State.TOUCHING_PIZZA:
            # if any pizza already has a scooper -> OK
            if any(pizza_has_scooper(p["bbox"]) for p in touched_pizzas):
                self.scooper_seen += 1
                if self.scooper_seen >= 3:
                    print("I saw the scooper 3 times")
                    self.state = State.IDLE
                    self.scooper_timer = 0
                    self.scooper_seen = 0
            else:
                self.scooper_timer -= 1
                if self.scooper_timer <= 0:
                    self.violation_seen = True
                    self.state = State.IDLE

        return (
            self.violation_seen,
            self.state,
            self.toppings_timer,
            self.move_timer,
            self.scooper_timer,
        )

    @staticmethod
    def _intersect(a, b):
        ax1, ay1, ax2, ay2 = map(float, a)
        bx1, by1, bx2, by2 = map(float, b)
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        return (ix2 - ix1) > 0 and (iy2 - iy1) > 0
