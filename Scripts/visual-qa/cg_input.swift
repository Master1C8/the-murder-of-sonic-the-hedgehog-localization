#!/usr/bin/env swift

import CoreGraphics
import Foundation

let eventSource = CGEventSource(stateID: .hidSystemState)

func usage() -> Never {
    fputs("usage: cg-input click|double-click|right-click|move X Y\n", stderr)
    fputs("       cg-input repeat-double-click X Y COUNT DELAY_MS\n", stderr)
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

func doubleClick(_ point: CGPoint) {
    click(point, button: .left, down: .leftMouseDown, up: .leftMouseUp)
    usleep(80_000)
    click(point, button: .left, down: .leftMouseDown, up: .leftMouseUp)
}

let arguments = Array(CommandLine.arguments.dropFirst())
guard let action = arguments.first else { usage() }

switch action {
case "click", "double-click", "right-click", "move":
    guard arguments.count == 3 else { usage() }
    let point = CGPoint(x: number(arguments[1]), y: number(arguments[2]))
    if action == "click" {
        click(point, button: .left, down: .leftMouseDown, up: .leftMouseUp)
    } else if action == "double-click" {
        doubleClick(point)
    } else if action == "right-click" {
        click(point, button: .right, down: .rightMouseDown, up: .rightMouseUp)
    } else {
        postMouse(.mouseMoved, .left, point)
    }
case "repeat-double-click":
    guard arguments.count == 5,
          let count = Int(arguments[3]), count > 0,
          let delayMilliseconds = Int(arguments[4]), delayMilliseconds >= 0 else {
        usage()
    }
    let point = CGPoint(x: number(arguments[1]), y: number(arguments[2]))
    for index in 0..<count {
        doubleClick(point)
        if index + 1 < count {
            usleep(useconds_t(delayMilliseconds) * 1_000)
        }
    }
default:
    usage()
}
