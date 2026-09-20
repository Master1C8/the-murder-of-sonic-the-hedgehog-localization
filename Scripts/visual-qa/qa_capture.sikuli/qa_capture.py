# Oculix runs this file through Jython 2.7. Keep it Python-2-compatible.
from sikuli import *
from java.io import File
from javax.imageio import ImageIO
import os
import subprocess
import sys
import time
import traceback


def fail(message, screen, runtime_dir):
    failure_path = os.path.join(runtime_dir, "failure.png")
    oculix_failure_path = os.path.join(runtime_dir, "oculix-failure.png")
    try:
        subprocess.call(["/usr/sbin/screencapture", "-x", failure_path])
    except Exception:
        pass
    try:
        screen.capture().save(runtime_dir, "oculix-failure.png")
    except Exception:
        pass
    print("VN_VISUAL_QA_FAILURE: " + message)
    sys.exit(2)


def find_marker(runtime_dir, timeout):
    pattern_path = os.path.join(runtime_dir, "templates", "2x", "main-menu.png")
    pattern = Pattern(pattern_path).similar(0.62)
    native_path = os.path.join(runtime_dir, "native-state.png")
    normalized_path = os.path.join(runtime_dir, "native-state-rgb.png")
    deadline = time.time() + timeout
    while time.time() <= deadline:
        subprocess.call(["/usr/sbin/screencapture", "-x", native_path])
        status = subprocess.call([
            "/opt/homebrew/bin/magick", native_path,
            "-alpha", "off", "-depth", "8", "PNG24:" + normalized_path,
        ])
        if status != 0:
            raise RuntimeError("could not normalize the native screenshot")
        finder = Finder(ImageIO.read(File(normalized_path)))
        try:
            finder.find(pattern)
            if finder.hasNext():
                return finder.next()
        finally:
            finder.destroy()
        wait(0.4)
    return None


def run_capture(screen, runtime_dir, code):
    status = subprocess.call([
        os.path.join(runtime_dir, "activate-app"),
        "com.Sonic-Social.The-Murder-of-Sonic-The-Hedgehog",
    ])
    if status != 0:
        fail("could not activate the game bundle", screen, runtime_dir)
    wait(2.0)
    if not find_marker(runtime_dir, 60):
        fail("main-menu marker did not appear", screen, runtime_dir)
    wait(1.0)
    output = os.path.join(runtime_dir, "raw", code + "-01-main-menu-raw.png")
    status = subprocess.call(["/usr/sbin/screencapture", "-x", output])
    if status != 0 or not os.path.exists(output):
        raise RuntimeError("native screenshot failed")
    print("VN_VISUAL_QA_CAPTURED: " + output)
    print("VN_VISUAL_QA_AUTOMATION_OK: " + code)


screen = Screen(0)
try:
    if len(sys.argv) != 4 or sys.argv[1] != "capture":
        raise RuntimeError("expected capture mode, runtime directory, and locale")
    run_capture(screen, sys.argv[2], sys.argv[3])
except SystemExit:
    raise
except BaseException as error:
    traceback.print_exc()
    fail(str(error), screen, sys.argv[2] if len(sys.argv) > 2 else "/private/tmp")
