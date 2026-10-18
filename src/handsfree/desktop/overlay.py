#!/usr/bin/env python3
"""Fullscreen, click-through overlay for calibration dots and the mouse grid.

Standalone script: it runs under the *system* Python (python-gobject and
gtk4-layer-shell from pacman) with LD_PRELOAD=libgtk4-layer-shell.so, which
gtk4-layer-shell requires. It reads JSON lines on stdin:

  {"mode": "dot", "x": 100, "y": 200, "label": "..."}
  {"mode": "grid", "cells": [[x, y, w, h], ...]}
  {"mode": "clear"}

Coordinates are monitor-local logical pixels. EOF on stdin quits.
"""

import argparse
import json
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_foreign("cairo")
import cairo  # noqa: E402
from gi.repository import Gdk, GLib, Gtk  # noqa: E402
from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402

CSS = "window.handsfree-overlay { background: transparent; }"


class Overlay:
    def __init__(self, app, monitor_name):
        self.state = {"mode": "clear"}
        win = Gtk.ApplicationWindow(application=app)
        win.add_css_class("handsfree-overlay")
        LayerShell.init_for_window(win)
        LayerShell.set_namespace(win, "handsfree")
        LayerShell.set_layer(win, LayerShell.Layer.OVERLAY)
        for edge in (LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM, LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT):
            LayerShell.set_anchor(win, edge, True)
        LayerShell.set_exclusive_zone(win, -1)
        LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.NONE)
        monitor = self._find_monitor(monitor_name)
        if monitor is not None:
            LayerShell.set_monitor(win, monitor)

        provider = Gtk.CssProvider()
        if hasattr(provider, "load_from_string"):  # GTK >= 4.12
            provider.load_from_string(CSS)
        else:
            provider.load_from_data(CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.area = Gtk.DrawingArea()
        self.area.set_draw_func(self.draw)
        win.set_child(self.area)
        win.connect("map", self._click_through)
        win.present()

    @staticmethod
    def _find_monitor(name):
        monitors = Gdk.Display.get_default().get_monitors()
        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            if monitor.get_connector() == name:
                return monitor
        return None

    @staticmethod
    def _click_through(win):
        # An empty input region lets every click fall through to the app below.
        win.get_surface().set_input_region(cairo.Region())

    def apply(self, message):
        self.state = message
        self.area.queue_draw()
        return False

    def draw(self, _area, cr, width, height):
        mode = self.state.get("mode")
        if mode == "dot":
            self._draw_dot(cr, width, height)
        elif mode == "grid":
            self._draw_grid(cr)

    def _draw_dot(self, cr, width, height):
        cr.set_source_rgba(0, 0, 0, 0.6)
        cr.paint()
        x, y = self.state["x"], self.state["y"]
        cr.set_source_rgba(1, 1, 1, 0.9)
        cr.arc(x, y, 18, 0, 6.2832)
        cr.set_line_width(3)
        cr.stroke()
        cr.set_source_rgba(0.88, 0.42, 0.46, 1)
        cr.arc(x, y, 6, 0, 6.2832)
        cr.fill()
        label = self.state.get("label", "")
        if label:
            cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            cr.set_font_size(22)
            extents = cr.text_extents(label)
            ty = height - 60 if y < height * 0.75 else 60
            cr.move_to((width - extents.width) / 2, ty)
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.show_text(label)

    def _draw_grid(self, cr):
        cr.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        for number, (x, y, w, h) in enumerate(self.state.get("cells", []), start=1):
            cr.rectangle(x, y, w, h)
            cr.set_source_rgba(0, 0, 0, 0.18)
            cr.fill_preserve()
            cr.set_source_rgba(1, 1, 1, 0.85)
            cr.set_line_width(2)
            cr.stroke()
            text = str(number)
            cr.set_font_size(max(12, min(56, min(w, h) * 0.4)))
            extents = cr.text_extents(text)
            tx = x + (w - extents.width) / 2 - extents.x_bearing
            ty = y + (h - extents.height) / 2 - extents.y_bearing
            cr.move_to(tx, ty)
            cr.text_path(text)
            cr.set_source_rgba(0, 0, 0, 0.8)
            cr.set_line_width(4)
            cr.stroke_preserve()
            cr.set_source_rgba(1, 1, 1, 1)
            cr.fill()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--monitor", default="")
    args = parser.parse_args()
    app = Gtk.Application(application_id="dev.omarchy.handsfree.overlay")
    holder = {}

    def activate(application):
        holder["overlay"] = Overlay(application, args.monitor)

        def read_stdin():
            for line in sys.stdin:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                GLib.idle_add(holder["overlay"].apply, message)
            GLib.idle_add(application.quit)

        threading.Thread(target=read_stdin, daemon=True).start()

    app.connect("activate", activate)
    app.run([])


if __name__ == "__main__":
    main()
