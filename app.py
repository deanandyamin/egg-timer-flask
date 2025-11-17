from flask import Flask, render_template, request, jsonify
import asyncio
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


# ============================================================
# 音效處理
# ============================================================
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
# Async 計時器（取代 threading 版本）
# ============================================================
class EggTimer:
    def __init__(self, size):
        self.size = size
        self.remain = 0
        self.flip_remain = 0

        self.running = False
        self.flip_running = False

        # 取代 Event，用 flag
        self.stop_main = False
        self.stop_flip = False

        # 10 / 60 / 120 秒倒數觸發管理
        self.fired_marks = {
            120: False,
            60: False,
            10: False,
        }

    def reset_marks(self):
        for k in self.fired_marks:
            self.fired_marks[k] = False

    async def start_main(self):
        while not self.stop_main and self.remain > 0:
            await asyncio.sleep(1)
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

        if self.stop_main:
            return

        # 完成
        queue_sound(f"finish_{self.size}.mp3")
        self.running = False
        self.remain = CONFIG[self.size]["main"]
        self.flip_remain = CONFIG[self.size]["flip"]

    async def start_flip(self):
        while not self.stop_flip and self.flip_remain > 0:
            await asyncio.sleep(1)
            self.flip_remain -= 1

        if self.stop_flip:
            return

        queue_sound(f"flip_{self.size}.mp3")
        self.flip_running = False
        self.flip_remain = CONFIG[self.size]["flip"]

    def start(self):
        self.remain = CONFIG[self.size]["main"]
        self.flip_remain = CONFIG[self.size]["flip"]

        self.running = True
        self.flip_running = True

        self.stop_main = False
        self.stop_flip = False
        self.reset_marks()

        asyncio.create_task(self.start_main())
        asyncio.create_task(self.start_flip())

        return resolve_sound(f"start_{self.size}.mp3")

    def reset(self):
        self.stop_main = True
        self.stop_flip = True

        self.running = False
        self.flip_running = False

        self.remain = CONFIG[self.size]["main"]
        self.flip_remain = CONFIG[self.size]["flip"]
        self.reset_marks()

        return resolve_sound(f"reset_{self.size}.mp3")


# ============================================================
# Loop Timer (async 版)
# ============================================================
class LoopTimer:
    def __init__(self):
        self.running = False
        self.stop_flag = False
        self.remain = 0
        self.fired10 = False

    async def loop_task(self):
        while not self.stop_flag:
            if self.remain == 0:
                queue_sound("loop_beep.mp3")
                self.remain = CONFIG["loop"]["main"]
                self.fired10 = False

            await asyncio.sleep(1)
            self.remain -= 1

            if self.remain == 10 and not self.fired10:
                queue_sound("countdown10.mp3")
                self.fired10 = True

        # reset 後結束
        return

    def start(self):
        if self.running:
            return None
        self.running = True
        self.stop_flag = False
        self.remain = CONFIG["loop"]["main"]
        self.fired10 = False

        asyncio.create_task(self.loop_task())
        return resolve_sound("loop_start.mp3")

    def reset(self):
        self.stop_flag = True
        self.running = False
        self.remain = CONFIG["loop"]["main"]
        self.fired10 = False
        return resolve_sound("loop_reset.mp3")


# ============================================================
# 建立 4 個 timer
# ============================================================
SmallTimer = EggTimer("small")
MediumTimer = EggTimer("medium")
LargeTimer = EggTimer("large")
Loop = LoopTimer()


# ============================================================
# Flask Routes
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

    if sz == "small":
        play = SmallTimer.start() if act == "start" else SmallTimer.reset()
    elif sz == "medium":
        play = MediumTimer.start() if act == "start" else MediumTimer.reset()
    elif sz == "large":
        play = LargeTimer.start() if act == "start" else LargeTimer.reset()
    elif sz == "loop":
        play = Loop.start() if act == "start" else Loop.reset()
    else:
        play = None

    return jsonify({"play_now": play})

if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run(host="0.0.0.0", port=8000, debug=True))
