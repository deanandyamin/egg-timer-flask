from flask import Flask, render_template, request, jsonify
import threading
import time
import json
import os

app = Flask(__name__)

CONFIG_FILE = "config.json"

DEFAULTS = {
    "small": {"main": 300, "flip": 30},
    "medium": {"main": 360, "flip": 40},
    "large": {"main": 420, "flip": 35},
    "loop": {"main": 180, "flip": 0},
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return DEFAULTS.copy()

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

CONFIG = load_config()

pending_sounds = []

def sound_exists(fname):
    return os.path.isfile(os.path.join(app.root_path, "static", fname))

def resolve_sound(fname):
    if sound_exists(fname):
        return fname

    if fname == "start_medium.mp3":
        return (
            "start_large.mp3"
            if sound_exists("start_large.mp3")
            else ("start_small.mp3" if sound_exists("start_small.mp3") else None)
        )

    if fname == "reset_medium.mp3":
        return (
            "reset_large.mp3"
            if sound_exists("reset_large.mp3")
            else ("reset_small.mp3" if sound_exists("reset_small.mp3") else None)
        )

    if fname in ["finish_small.mp3", "finish_medium.mp3", "finish_large.mp3"]:
        return "loop_beep.mp3" if sound_exists("loop_beep.mp3") else None

    return None

def queue_sound(fname):
    resolved = resolve_sound(fname)
    if not resolved:
        return

    if resolved == "countdown10.mp3" and resolved in pending_sounds:
        return

    pending_sounds.append(resolved)


# ============================================================
# ⭐⭐⭐ 抽象化計時器：小/中/大共用同一套邏輯 ⭐⭐⭐
# ============================================================

class EggTimer:
    def __init__(self, size):
        self.size = size
        self.remain = 0
        self.flip_remain = 0
        self.running = False
        self.flip_running = False

        self.stop_event = threading.Event()
        self.flip_stop_event = threading.Event()

        # 倒數 10 秒、60 秒、120 秒只觸發一次
        self.fired_marks = {
            120: False,
            60: False,
            10: False,
        }

    def reset_marks(self):
        for k in self.fired_marks:
            self.fired_marks[k] = False

    def start(self):
        self.remain = CONFIG[self.size]["main"]
        self.flip_remain = CONFIG[self.size]["flip"]
        self.running = True
        self.flip_running = True
        self.reset_marks()

        self.stop_event.clear()
        self.flip_stop_event.clear()

        threading.Thread(target=self.run_main_timer, daemon=True).start()
        threading.Thread(target=self.run_flip_timer, daemon=True).start()

        return resolve_sound(f"start_{self.size}.mp3")

    def reset(self):
        self.running = False
        self.flip_running = False

        self.stop_event.set()
        self.flip_stop_event.set()

        self.remain = CONFIG[self.size]["main"]
        self.flip_remain = CONFIG[self.size]["flip"]
        self.reset_marks()

        return resolve_sound(f"reset_{self.size}.mp3")

    # -------------------------------------------
    # 主計時器 thread
    # -------------------------------------------
    def run_main_timer(self):
        while not self.stop_event.is_set() and self.remain > 0:
            if self.stop_event.wait(1):
                return

            self.remain -= 1
            r = self.remain

            if r in self.fired_marks and not self.fired_marks[r]:
                fname = (
                    "countdown02.mp3" if r == 120 else
                    "countdown01.mp3" if r == 60 else
                    "countdown10.mp3"
                )
                queue_sound(fname)
                self.fired_marks[r] = True

        if self.stop_event.is_set():
            return

        # 正常結束
        self.running = False
        self.remain = CONFIG[self.size]["main"]
        self.flip_remain = CONFIG[self.size]["flip"]
        queue_sound(f"finish_{self.size}.mp3")

    # -------------------------------------------
    # 翻面計時器 thread
    # -------------------------------------------
    def run_flip_timer(self):
        while not self.flip_stop_event.is_set() and self.flip_remain > 0:
            if self.flip_stop_event.wait(1):
                return

            self.flip_remain -= 1

        if self.flip_stop_event.is_set():
            return

        # 翻面提示
        queue_sound(f"flip_{self.size}.mp3")
        self.flip_running = False
        self.flip_remain = CONFIG[self.size]["flip"]


# ============================================================
# ⭐⭐⭐ 建立三組計時器實例 ⭐⭐⭐
# ============================================================

SmallTimer = EggTimer("small")
MediumTimer = EggTimer("medium")
LargeTimer = EggTimer("large")


# ============================================================
# ⭐⭐⭐ Loop 計時器（獨立） ⭐⭐⭐
# ============================================================

class LoopTimer:
    def __init__(self):
        self.remain = 0
        self.running = False
        self.stop_event = threading.Event()
        self.fired_10 = False

    def start(self):
        if self.running:
            return None

        self.running = True
        self.stop_event.clear()
        self.remain = CONFIG["loop"]["main"]
        self.fired_10 = False

        threading.Thread(target=self.run_loop, daemon=True).start()
        return resolve_sound("loop_start.mp3")

    def reset(self):
        self.running = False
        self.stop_event.set()
        self.remain = CONFIG["loop"]["main"]
        self.fired_10 = False
        return resolve_sound("loop_reset.mp3")

    def run_loop(self):
        while not self.stop_event.is_set():
            if self.remain == 0:
                queue_sound("loop_beep.mp3")
                self.remain = CONFIG["loop"]["main"]
                self.fired_10 = False

            if self.stop_event.wait(1):
                return

            self.remain -= 1
            if self.remain < 0:
                self.remain = 0

            if self.remain == 10 and not self.fired_10:
                queue_sound("countdown10.mp3")
                self.fired_10 = True


Loop = LoopTimer()


# ============================================================
# ⭐⭐⭐ Flask Routes ⭐⭐⭐
# ============================================================

@app.route("/")
def index():
    return render_template("template.html", config=CONFIG)

@app.route("/setcfg", methods=["POST"])
def setcfg():
    global CONFIG
    CONFIG = request.json
    save_config(CONFIG)
    return jsonify({"ok": True})

@app.route("/status")
def status():
    out = {
        "small": {"remain": SmallTimer.remain, "flip_remain": SmallTimer.flip_remain},
        "medium": {"remain": MediumTimer.remain, "flip_remain": MediumTimer.flip_remain},
        "large": {"remain": LargeTimer.remain, "flip_remain": LargeTimer.flip_remain},
        "loop": Loop.remain,
    }

    sounds = []
    while pending_sounds:
        sounds.append(pending_sounds.pop(0))
    out["sounds"] = sounds

    return jsonify(out)

@app.route("/action", methods=["POST"])
def action():
    d = request.json
    sz = d["size"]
    act = d["act"]

    play_now = None

    if sz == "small":
        play_now = SmallTimer.start() if act == "start" else SmallTimer.reset()

    elif sz == "medium":
        play_now = MediumTimer.start() if act == "start" else MediumTimer.reset()

    elif sz == "large":
        play_now = LargeTimer.start() if act == "start" else LargeTimer.reset()

    elif sz == "loop":
        play_now = Loop.start() if act == "start" else Loop.reset()

    return jsonify({"play_now": play_now}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
