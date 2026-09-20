#!/usr/bin/env swift

import CoreGraphics
import Foundation

let eventSource = CGEventSource(stateID: .hidSystemState)

func usage() -> Never {
    fputs("usage: cg-input click|right-click|move X Y\n", stderr)
    exit(64)
}

func number(_ value: String) -> CGFloat {
    guard let parsed = Double(value) else { usage() }
    return CGFloat(parsed)
}

func postMouse(_ type: CGEventType, _ button: CGMouseButton, _ point: CGPoint) {
    guard let event = CGEvent(
        mouseEventSource: eventSource,
        mouseType: type,
        mouseCursorPosition: point,
        mouseButton: button
    ) else {
        fputs("could not create mouse event\n", stderr)
        exit(1)
    }
    event.post(tap: .cghidEventTap)
}

func click(_ point: CGPoint, button: CGMouseButton, down: CGEventType, up: CGEventType) {
    postMouse(.mouseMoved, .left, point)
    usleep(50_000)
    postMouse(down, button, point)
    usleep(60_000)
    postMouse(up, button, point)
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard let action = arguments.first else { usage() }

switch action {
case "click", "right-click", "move":
    guard arguments.count == 3 else { usage() }
    let point = CGPoint(x: number(arguments[1]), y: number(arguments[2]))
    if action == "click" {
        click(point, button: .left, down: .leftMouseDown, up: .leftMouseUp)
    } else if action == "right-click" {
        click(point, button: .right, down: .rightMouseDown, up: .rightMouseUp)
    } else {
        postMouse(.mouseMoved, .left, point)
    }
default:
    usage()
}
