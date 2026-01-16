import time
import sys
from pathlib import Path
import threading

import pyautogui
import mss
import cv2
import numpy as np
import keyboard  # pip install keyboard

MY_RACE = "tauren"  # options: orc, undead, tauren, troll, blood_elf
MY_CLASS = "warrior"  # options: warrior, hunter, rogue, mage, priest, warlock, shaman, paladin
MY_NAME = "Moothecowman"  # desired character name

# ------------------- settings -------------------
pyautogui.FAILSAFE = True  # move mouse to top-left corner to abort
pyautogui.PAUSE = 0.02

# Your monitor layout (from your debug):
#  0 = virtual (all)
#  1 = RIGHT monitor (left=1920)
#  2 = LEFT/PRIMARY (left=0)
WOW_MONITOR = 1  # <-- set to 2 if WoW is on the left/primary monitor

CONFIDENCE = 0.8
POLL = 0.12

# Hotkeys
HOTKEY_TOGGLE = "f8"
HOTKEY_EXIT = "f9"

# ------------------- paths -------------------
BASE_DIR = Path(__file__).resolve().parent
IMG_DIR = BASE_DIR / "images"


def img(name: str) -> str:
    return str(IMG_DIR / name)


# ------------------- images -------------------
CHANGE_REALM = img("change_realm_button.png")
REALM_SELECTION = img("realm_selection.png")

CHOICE_IMAGES = [
    img("spine_shatter_unselected.png"),
    img("spine_shatter_selected.png"),
]

BODY_MALE = img("body_male.png")

AGREE = img("agree.png")

ESC_OR_LOOP_IMAGES = [
    img("horde_not_available.png"),  # if found -> Esc and loop
    img("orc.png"),
]

RACE_IMAGES = {
    "orc": img("orc.png"),
    "undead": img("undead.png"),
    "tauren": img("tauren.png"),
    "troll": img("troll.png"),
    "blood_elf": img("bloodelf.png"),
}

CLASS_IMAGES = {
    "warrior": img("warrior.png"),
    "hunter": img("hunter.png"),
    "rogue": img("rogue.png"),
    "mage": img("mage.png"),
    "priest": img("priest.png"),
    "warlock": img("warlock.png"),
    "shaman": img("shaman.png"),
    "paladin": img("paladin.png"),
}


# ------------------- MSS + OpenCV matching -------------------
def _grab_monitor_bgr(monitor_index: int) -> tuple[dict, np.ndarray]:
    with mss.mss() as sct:
        mon = sct.monitors[monitor_index]
        shot = sct.grab(mon)  # BGRA
        bgr = np.array(shot)[:, :, :3]  # BGR
        return mon, bgr


def locate_center_mss(
    image_path: str,
    confidence: float = CONFIDENCE,
    monitor_index: int = WOW_MONITOR,
    grayscale: bool = False,
) -> pyautogui.Point | None:

    print(
        f"\tLocating image: {image_path} on monitor {monitor_index} (grayscale={grayscale})"
    )

    template = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if template is None:
        raise FileNotFoundError(f"Template not found or unreadable: {image_path}")

    mon, hay_bgr = _grab_monitor_bgr(monitor_index)

    time.sleep(0.1)  # slight delay to allow screen to update
    pyautogui.moveTo(mon["left"] + 1, 1)  # prevent failsafe trigger during screenshot
    time.sleep(0.1)  # slight delay to allow screen to update
    if grayscale:
        hay = cv2.cvtColor(hay_bgr, cv2.COLOR_BGR2GRAY)
        tmpl = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    else:
        hay = hay_bgr
        tmpl = template

    th, tw = tmpl.shape[:2]
    hh, hw = hay.shape[:2]
    if tw > hw or th > hh:
        return None

    res = cv2.matchTemplate(hay, tmpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val < confidence:
        return None
    else:
        print(f"\t\tFound with confidence {max_val:.3f}")

    x = mon["left"] + max_loc[0] + tw // 2
    y = mon["top"] + max_loc[1] + th // 2
    return pyautogui.Point(x, y)


def wait_for_mss(
    image_path: str, timeout: float = 10.0, **kwargs
) -> pyautogui.Point | None:
    end = time.time() + timeout
    while time.time() < end:
        pt = locate_center_mss(image_path, **kwargs)
        if pt:
            return pt
        time.sleep(POLL)
    return None


def wait_for_any_mss(
    image_paths: list[str], timeout: float = 10.0, **kwargs
) -> tuple[str | None, pyautogui.Point | None]:
    end = time.time() + timeout
    while time.time() < end:
        for p in image_paths:
            pt = locate_center_mss(p, **kwargs)
            if pt:
                return p, pt
        time.sleep(POLL)
    return None, None


# ------------------- input actions -------------------
def click_center(pt: pyautogui.Point):
    pyautogui.click(pt.x, pt.y)


def double_click_center(pt: pyautogui.Point):
    pyautogui.doubleClick(pt.x, pt.y)


def create_character():
    print("HORDE AVAILABLE detected, proceeding with character creation...")
    race_pt = locate_center_mss(
        RACE_IMAGES[MY_RACE],
        confidence=0.95,
        monitor_index=WOW_MONITOR,
        grayscale=False,
    )

    if race_pt:
        print(f"Located race point: {race_pt} {MY_RACE}")
        click_center(race_pt)
        time.sleep(1)
        class_pt = locate_center_mss(
            CLASS_IMAGES[MY_CLASS],
            confidence=CONFIDENCE,
            monitor_index=WOW_MONITOR,
            grayscale=False,
        )
        if class_pt:
            click_center(class_pt)
            time.sleep(0.5)
            pyautogui.typewrite(MY_NAME)
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(0.5)
            again_pt = locate_center_mss(AGREE, confidence=CONFIDENCE, monitor_index=WOW_MONITOR, grayscale=False)
            if again_pt:
                click_center(again_pt)
                print("Clicked AGREE button.")

    time.sleep(0.5)


# ------------------- run control -------------------
run_event = threading.Event()  # set => running, cleared => paused
stop_event = threading.Event()  # set => exit program


def toggle_run():
    if run_event.is_set():
        run_event.clear()
        print("[PAUSED] (press F8 to run)")
    else:
        run_event.set()
        print("[RUNNING] (press F8 to pause)")


def request_exit():
    print("[EXIT] stopping...")
    stop_event.set()
    run_event.set()  # unblock if paused


# ------------------- main loop -------------------
def automation_loop():
    print(f"Using monitor index {WOW_MONITOR} for WoW.")
    print(f"Confidence={CONFIDENCE}  Poll={POLL}s")
    print(f"Hotkeys: {HOTKEY_TOGGLE}=toggle run/pause, {HOTKEY_EXIT}=exit")
    print("Starts PAUSED. Move mouse to TOP-LEFT to abort (pyautogui failsafe).")
    print()

    while not stop_event.is_set():
        # If paused, sleep lightly until resumed or exit requested
        if not run_event.is_set():
            time.sleep(0.05)
            continue

        time.sleep(1)
        # 1) detect change realm button; if exists click
        pt = locate_center_mss(
            CHANGE_REALM,
            confidence=CONFIDENCE - 0.2,
            monitor_index=WOW_MONITOR,
            grayscale=False,
        )
        if pt:
            time.sleep(0.3)
            click_center(pt)
            time.sleep(POLL)
            click_center(pt)
            time.sleep(0.5)

            # wait for realm selection
            if not wait_for_mss(
                REALM_SELECTION,
                timeout=12,
                confidence=CONFIDENCE,
                monitor_index=WOW_MONITOR,
                grayscale=False,
            ):
                time.sleep(0.2)
                continue

            # find either of two images; double click + Enter
            found_path, pt_choice = wait_for_any_mss(
                CHOICE_IMAGES,
                timeout=8,
                confidence=CONFIDENCE,
                monitor_index=WOW_MONITOR,
                grayscale=False,
            )
            if found_path and pt_choice:
                # double_click_center(pt_choice)
                click_center(pt_choice)  # single click to avoid issues
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(0.1)
                pyautogui.press("enter")
            else:
                time.sleep(0.2)
                continue

        # 2) branch checks
        body_pt = locate_center_mss(
            BODY_MALE,
            confidence=CONFIDENCE - 0.15,
            monitor_index=WOW_MONITOR,
            grayscale=False,
        )
        if body_pt:
            click_center(body_pt)
            time.sleep(0.3)

        if locate_center_mss(
            ESC_OR_LOOP_IMAGES[0],
            confidence=CONFIDENCE,
            monitor_index=WOW_MONITOR,
            grayscale=False,
        ):
            time.sleep(1)
            pyautogui.press("esc")
            print('"Horde not available" detected, pressed Esc and looping...')
            continue

        if locate_center_mss(
            ESC_OR_LOOP_IMAGES[1],
            confidence=0.95,
            monitor_index=WOW_MONITOR,
            grayscale=False,
        ):
            create_character()
        else:
            time.sleep(0.15)


# ------------------- entrypoint -------------------
if __name__ == "__main__":
    try:
        # Register hotkeys
        keyboard.add_hotkey(HOTKEY_TOGGLE, toggle_run)
        keyboard.add_hotkey(HOTKEY_EXIT, request_exit)

        # Run automation in a background thread, keep main thread for hotkeys
        t = threading.Thread(target=automation_loop, daemon=True)
        t.start()

        # Block until exit requested
        keyboard.wait(HOTKEY_EXIT)
        request_exit()
        time.sleep(0.2)
        sys.exit(0)

    except KeyboardInterrupt:
        request_exit()
        sys.exit(0)
