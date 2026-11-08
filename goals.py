import json
import os
from datetime import date

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


def load():
    if os.path.exists(FILE):
        with open(FILE) as f:
            data = json.load(f)
        # old goals did not track the stars they earned
        for g in data["goals"]:
            if "earned" not in g:
                g["earned"] = g["stars"] if g["last_done"] else 0
        return data
    return {"total_stars": 0, "goals": []}


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_goal(data, name, stars, kind="daily"):
    # kind is "daily" (can be ticked once every day) or "once" (one time only)
    data["goals"].append({
        "name": name,
        "stars": stars,
        "kind": kind,
        "last_done": None,
        "earned": 0,
    })
    save(data)


def delete_goal(data, index):
    goal = data["goals"].pop(index)
    # take back the stars this goal gave you
    data["total_stars"] = max(0, data["total_stars"] - goal.get("earned", 0))
    save(data)


def can_tick(goal):
    today = str(date.today())
    if goal["kind"] == "daily":
        return goal["last_done"] != today
    return goal["last_done"] is None


def tick(data, index):
    goal = data["goals"][index]
    if not can_tick(goal):
        return 0
    goal["last_done"] = str(date.today())
    goal["earned"] = goal.get("earned", 0) + goal["stars"]
    data["total_stars"] += goal["stars"]
    save(data)
    return goal["stars"]


def untick(data, index):
    goal = data["goals"][index]
    if can_tick(goal):
        return 0  # nothing to untick
    goal["last_done"] = None
    goal["earned"] = max(0, goal.get("earned", 0) - goal["stars"])
    data["total_stars"] = max(0, data["total_stars"] - goal["stars"])
    save(data)
    return goal["stars"]

def edit_goal(data, index, name, stars, kind):
    goal = data["goals"][index]
    if not can_tick(goal):
        # already ticked, so fix the stars it gave
        diff = stars - goal["stars"]
        goal["earned"] = max(0, goal.get("earned", 0) + diff)
        data["total_stars"] = max(0, data["total_stars"] + diff)
    goal["name"] = name
    goal["stars"] = stars
    goal["kind"] = kind
    save(data)

# ---------- small test menu (only runs when you run this file directly) ----------
if __name__ == "__main__":
    data = load()
    while True:
        print("\nTotal stars:", data["total_stars"])
        for i, g in enumerate(data["goals"]):
            mark = "[ ]" if can_tick(g) else "[x]"
            print(i, mark, g["name"], "-", g["stars"], "stars", "(" + g["kind"] + ")")
        print("a = add goal, t = tick, u = untick, d = delete goal, q = quit")
        choice = input("> ").strip()
        if choice == "a":
            name = input("Goal name: ")
            stars = int(input("Stars: "))
            kind = input("daily or once: ").strip() or "daily"
            add_goal(data, name, stars, kind)
        elif choice == "t":
            earned = tick(data, int(input("Goal number: ")))
            print("You earned", earned, "stars!" if earned else "(already done)")
        elif choice == "u":
            removed = untick(data, int(input("Goal number: ")))
            print("Removed", removed, "stars" if removed else "(nothing to untick)")
        elif choice == "d":
            delete_goal(data, int(input("Goal number: ")))
        elif choice == "q":
            break