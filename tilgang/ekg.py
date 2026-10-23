"""The Medicus loading animation for GTK: a heartbeat (ECG) line with a pulse running across it.

Same shape and timing as the web version (medicus/static/common.js) and the start-up
animation (branding/make_assets.py), so loading looks the same everywhere.
"""

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

# One heartbeat, as (x, y) fractions: flat, P wave, QRS spike, T wave, flat.
SHAPE = [(0.00, 0), (0.30, 0), (0.33, -0.10), (0.36, 0), (0.42, 0), (0.44, 0.12), (0.47, -1.0),
         (0.50, 0.35), (0.53, 0), (0.60, 0), (0.66, -0.22), (0.72, 0), (1.00, 0)]
GREEN = (127 / 255, 224 / 255, 173 / 255)
PERIOD = 1.4  # seconds per sweep
TAIL = 0.32   # length of the bright pulse, as a fraction of the line


def point_at(t: float) -> float:
    for (x0, y0), (x1, y1) in zip(SHAPE, SHAPE[1:]):
        if x0 <= t <= x1:
            return y0 + (y1 - y0) * (t - x0) / (x1 - x0)
    return 0.0


class Ekg(Gtk.DrawingArea):
    def __init__(self, width=120, height=34, color=GREEN):
        super().__init__(content_width=width, content_height=height)
        self.color = color
        self.phase = 0.0
        self.set_draw_func(self._draw)
        self.add_tick_callback(self._tick)

    def _tick(self, _widget, clock):
        self.phase = (clock.get_frame_time() / 1e6 % PERIOD) / PERIOD
        self.queue_draw()
        return True

    def _draw(self, _area, cr, width, height):
        base, amp = height * 0.65, height * 0.55
        steps = 120
        points = [(i / steps * width, base + amp * point_at(i / steps)) for i in range(steps + 1)]
        cr.set_line_width(2.2)
        cr.set_line_cap(1)  # round
        cr.set_line_join(1)
        # faint full trace
        cr.set_source_rgba(*self.color, 0.22)
        cr.move_to(*points[0])
        for p in points[1:]:
            cr.line_to(*p)
        cr.stroke()
        # bright pulse fading out behind its head
        head = int(self.phase * (1 + TAIL) * steps)
        tail = int(TAIL * steps)
        for i in range(max(1, head - tail), min(head, steps) + 1):
            alpha = 1 - (head - i) / tail
            cr.set_source_rgba(*self.color, max(0.0, alpha))
            cr.move_to(*points[i - 1])
            cr.line_to(*points[i])
            cr.stroke()
        if 0 < head <= steps:
            x, y = points[head]
            cr.set_source_rgba(1, 1, 1, 1)
            cr.arc(x, y, 2.6, 0, 6.2832)
            cr.fill()
