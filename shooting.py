import math
import random
import pygame

SHOOT_AT = 500       # stars needed before shooting stars start
SHOOT_EVERY = 20     # about one shooting star every 20 seconds


class ShootingStars:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.items = []

    def spawn(self):
        angle = math.radians(random.uniform(20, 45))
        direction = random.choice([-1, 1])
        speed = random.uniform(1000, 1500)
        self.items.append({
            "x": random.uniform(0.1, 0.9) * self.width,
            "y": random.uniform(0.08, 0.5) * self.height,
            "vx": math.cos(angle) * speed * direction,
            "vy": math.sin(angle) * speed,
            "life": random.uniform(0.5, 0.8),
            "age": 0.0,
        })

    def update(self, total_stars):
        dt = 1 / 30
        if total_stars >= SHOOT_AT and random.random() < dt / SHOOT_EVERY:
            self.spawn()
        for s in self.items:
            s["x"] += s["vx"] * dt
            s["y"] += s["vy"] * dt
            s["age"] += dt
        self.items = [s for s in self.items if s["age"] < s["life"]]

    def draw(self, screen):
        for s in self.items:
            fade = math.sin(math.pi * min(1.0, s["age"] / s["life"]))
            n = 14
            for k in range(n):
                f0 = k / n
                f1 = (k + 1) / n
                x0 = s["x"] - s["vx"] * 0.12 * f0
                y0 = s["y"] - s["vy"] * 0.12 * f0
                x1 = s["x"] - s["vx"] * 0.12 * f1
                y1 = s["y"] - s["vy"] * 0.12 * f1
                b = (1 - f0) * fade
                color = (int(255 * b), int(245 * b), int(225 * b))
                pygame.draw.line(screen, color, (x0, y0), (x1, y1), 2 if k < 5 else 1)
            pygame.draw.circle(screen, (255, 250, 240), (int(s["x"]), int(s["y"])), 2)