import json
import os
from datetime import date

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


def today():
    return str(date.today())


def load():
    if os.path.exists(FILE):
        with open(FILE) as f:
            data = json.load(f)
        for g in data["goals"]:
            if "earned" not in g:
                g["earned"] = g["stars"] if g["last_done"] else 0
            if "count" not in g:
                if g["kind"] == "once":
                    g["count"] = 1 if g["last_done"] else 0
                else:
                    g["count"] = 1 if g["last_done"] == today() else 0
        return data
    return {"total_stars": 0, "goals": []}


def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_goal(data, name, stars, kind="daily"):
    # kind is "daily" (can be ticked many times a day) or "once" (one time only)
    data["goals"].append({
        "name": name,
        "stars": stars,
        "kind": kind,
        "last_done": None,
        "earned": 0,
        "count": 0,
    })
    save(data)


def delete_goal(data, index):
    goal = data["goals"].pop(index)
    # take back the stars this goal gave you
    data["total_stars"] = max(0, data["total_stars"] - goal.get("earned", 0))
    save(data)


def today_count(goal):
    # how many times this goal is ticked today (once goals: 1 if finished)
    if goal["kind"] == "once":
        return 1 if goal["last_done"] else 0
    if goal["last_done"] == today():
        return goal.get("count", 1)
    return 0


def is_done(goal):
    return today_count(goal) > 0


def can_tick(goal):
    if goal["kind"] == "daily":
        return True  # daily goals can be ticked again and again
    return goal["last_done"] is None


def tick(data, index):
    goal = data["goals"][index]
    if not can_tick(goal):
        return 0
    if goal["kind"] == "daily":
        if goal["last_done"] != today():
            goal["count"] = 0  # a new day starts from zero
        goal["count"] = goal.get("count", 0) + 1
    else:
        goal["count"] = 1
    goal["last_done"] = today()
    goal["earned"] = goal.get("earned", 0) + goal["stars"]
    data["total_stars"] += goal["stars"]
    save(data)
    return goal["stars"]


def untick(data, index):
    # takes back ONE tick
    goal = data["goals"][index]
    if today_count(goal) == 0:
        return 0
    if goal["kind"] == "daily":
        goal["count"] -= 1
        if goal["count"] <= 0:
            goal["count"] = 0
            goal["last_done"] = None
    else:
        goal["count"] = 0
        goal["last_done"] = None
    goal["earned"] = max(0, goal.get("earned", 0) - goal["stars"])
    data["total_stars"] = max(0, data["total_stars"] - goal["stars"])
    save(data)
    return goal["stars"]


def edit_goal(data, index, name, stars, kind):
    goal = data["goals"][index]
    n = today_count(goal)
    # if it is ticked, fix the stars it gave
    diff = (stars - goal["stars"]) * n
    if diff:
        goal["earned"] = max(0, goal.get("earned", 0) + diff)
        data["total_stars"] = max(0, data["total_stars"] + diff)
    if kind != goal["kind"]:
        if kind == "once":
            if n == 0:
                goal["last_done"] = None
            goal["count"] = 1 if goal["last_done"] else 0
        else:
            goal["count"] = 1 if goal["last_done"] == today() else 0
        goal["kind"] = kind
    goal["name"] = name
    goal["stars"] = stars
    save(data)


def move_to(data, index, new_index):
    # move one goal to a new position (used while dragging, so it does not save;
    # call save(data) when the drag ends)
    goals_list = data["goals"]
    new_index = max(0, min(new_index, len(goals_list) - 1))
    if new_index == index:
        return index
    goals_list.insert(new_index, goals_list.pop(index))
    return new_index


def auto_sort(data):
    # unfinished goals go to the top, finished ones sink to the bottom.
    # The sort is stable, so the order you picked by dragging is kept inside each group.
    # Returns True if anything moved.
    before = [id(g) for g in data["goals"]]
    data["goals"].sort(key=is_done)
    if before != [id(g) for g in data["goals"]]:
        save(data)
        return True
    return False


# ---------- small test menu (only runs when you run this file directly) ----------
if __name__ == "__main__":
    data = load()
    while True:
        print("\nTotal stars:", data["total_stars"])
        for i, g in enumerate(data["goals"]):
            n = today_count(g)
            extra = " x" + str(n) if n and g["kind"] == "daily" else ""
            print(i, "[x]" if n else "[ ]", g["name"], "-", g["stars"], "stars",
                  "(" + g["kind"] + ")" + extra)
        print("a = add, t = tick, u = untick one, d = delete, s = sort, q = quit")
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
        elif choice == "s":
            auto_sort(data)
        elif choice == "q":
            break