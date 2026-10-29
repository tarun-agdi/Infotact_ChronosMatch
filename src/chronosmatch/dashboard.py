
import curses
import time
from collections import deque
from datetime import datetime


class CursesDashboard:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.orders = 0
        self.trades = 0
        self.status = "STARTING"
        self.latency_us = None
        self.start_time = time.monotonic()
        self.recent_trades = deque(maxlen=6)

        self.last_rate_time = time.monotonic()
        self.last_rate_orders = 0
        self.orders_per_sec = 0.0

        # Configure the terminal
        self.stdscr.nodelay(True)
        self.stdscr.keypad(True)
        self.setup_colors()

        try:
            curses.curs_set(0)
        except curses.error:
            pass

    def setup_colors(self):
        # Use colors when the terminal supports them
        try:
            if curses.has_colors():
                curses.start_color()
                curses.use_default_colors()
                curses.init_pair(1, curses.COLOR_GREEN, -1)
                curses.init_pair(2, curses.COLOR_CYAN, -1)
                curses.init_pair(3, curses.COLOR_YELLOW, -1)
                curses.init_pair(4, curses.COLOR_RED, -1)
                self.colors = True
            else:
                self.colors = False
        except curses.error:
            self.colors = False

    def color(self, pair, bold=False):
        # Return a safe text style
        style = curses.A_BOLD if bold else curses.A_NORMAL
        if self.colors:
            style |= curses.color_pair(pair)
        return style

    def put(self, y, x, text, style=0, max_width=None):
        # Avoid writing outside the terminal
        height, width = self.stdscr.getmaxyx()

        if y < 0 or y >= height or x < 0 or x >= width:
            return

        available = width - x - 1
        if max_width is not None:
            available = min(available, max_width)

        if available <= 0:
            return

        try:
            self.stdscr.addstr(y, x, str(text)[:available], style)
        except curses.error:
            pass

    def draw_panel(self, y, x, height, width, title):
        # Draw a bordered panel
        screen_h, screen_w = self.stdscr.getmaxyx()

        if height < 2 or width < 2:
            return False
        if y < 0 or x < 0:
            return False
        if y + height > screen_h or x + width > screen_w:
            return False

        try:
            self.stdscr.addstr(y, x, "+" + "-" * (width - 2) + "+")
            for row in range(y + 1, y + height - 1):
                self.stdscr.addstr(row, x, "|")
                self.stdscr.addstr(row, x + width - 1, "|")
            self.stdscr.addstr(
                y + height - 1, x, "+" + "-" * (width - 2) + "+"
            )
        except curses.error:
            pass

        self.put(y, x + 2, f" {title} ", self.color(2, True), width - 4)
        return True

    def update_rate(self):
        # Calculate throughput from newly processed orders
        now = time.monotonic()
        elapsed = now - self.last_rate_time

        if elapsed >= 1.0:
            new_orders = max(0, self.orders - self.last_rate_orders)
            self.orders_per_sec = new_orders / elapsed
            self.last_rate_orders = self.orders
            self.last_rate_time = now

    def draw_header(self, width):
        # Display the title and current clock
        self.put(0, 2, "CHRONOSMATCH", self.color(2, True))
        self.put(0, 16, "ZERO-COPY HFT ENGINE", self.color(2))
        self.put(0, max(2, width - 22),
                 datetime.now().strftime("%H:%M:%S"),
                 self.color(3, True))
        self.put(1, 2, "=" * max(1, width - 4))

    def draw_metrics(self, width):
        # Display core engine metrics
        panel_width = max(1, (width - 6) // 2)
        left_x = 2
        right_x = left_x + panel_width + 2

        self.draw_panel(3, left_x, 8, panel_width, "ENGINE")
        self.draw_panel(3, right_x, 8, panel_width, "PERFORMANCE")

        status_color = 1 if self.status == "RUNNING" else 3
        self.put(5, left_x + 2, f"Status     : {self.status}",
                 self.color(status_color, True), panel_width - 4)
        self.put(6, left_x + 2,
                 f"Orders     : {self.orders:,}",
                 max_width=panel_width - 4)
        self.put(7, left_x + 2,
                 f"Trades     : {self.trades:,}",
                 max_width=panel_width - 4)

        uptime = time.monotonic() - self.start_time
        minutes, seconds = divmod(int(uptime), 60)
        hours, minutes = divmod(minutes, 60)
        self.put(8, left_x + 2,
                 f"Uptime     : {hours:02}:{minutes:02}:{seconds:02}",
                 max_width=panel_width - 4)

        self.put(5, right_x + 2,
                 f"Orders/sec : {self.orders_per_sec:,.1f}",
                 self.color(1, True), panel_width - 4)
        latency = (
            f"{self.latency_us:.2f} us"
            if self.latency_us is not None
            else "Awaiting data"
        )
        self.put(6, right_x + 2, f"Latency    : {latency}",
                 max_width=panel_width - 4)
        self.put(7, right_x + 2,
                 "Mode       : LIVE METRICS",
                 self.color(2), panel_width - 4)
        self.put(8, right_x + 2,
                 "Feed       : Pipeline required",
                 max_width=panel_width - 4)

    def draw_trades(self, width, height):
        # Display the most recent executions
        y = 13
        panel_height = max(3, height - y - 3)

        if not self.draw_panel(y, 2, panel_height, width - 4,
                               "RECENT TRADES"):
            return

        self.put(y + 1, 4,
                 f"{'TIME':<10} {'SYMBOL':<10} {'SIDE':<6} "
                 f"{'PRICE':>10} {'QTY':>8}",
                 self.color(3, True), width - 8)

        rows = min(len(self.recent_trades), panel_height - 3)

        for i, trade in enumerate(list(self.recent_trades)[-rows:]):
            row_y = y + 2 + i
            self.put(row_y, 4, trade, max_width=width - 8)

    def draw_footer(self, height, width):
        # Show shortcuts at the bottom
        self.put(height - 2, 2,
                 "Q: Quit   R: Redraw   Ctrl+C: Exit",
                 self.color(3), width - 4)
        self.put(height - 1, 2,
                 "ChronosMatch | Terminal Monitor",
                 max_width=width - 4)

    def refresh(self):
        # Redraw the dashboard without changing engine data
        self.update_rate()
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()

        if height < 20 or width < 70:
            self.put(0, 0, "Terminal too small. Resize to at least 70x20.")
            self.stdscr.refresh()
            return

        self.draw_header(width)
        self.draw_metrics(width)
        self.draw_trades(width, height)
        self.draw_footer(height, width)
        self.stdscr.refresh()

    def update(self, orders=None, trades=None, status=None,
               latency_us=None):
        # Update supplied values; counters are absolute totals
        if orders is not None:
            self.orders = max(0, orders)
        if trades is not None:
            self.trades = max(0, trades)
        if status is not None:
            self.status = status
        if latency_us is not None:
            self.latency_us = latency_us

    def add_trade(self, trade):
        # Accept a dictionary or a plain text trade record
        if isinstance(trade, dict):
            timestamp = trade.get(
                "time", datetime.now().strftime("%H:%M:%S")
            )
            symbol = trade.get("symbol", "N/A")
            side = trade.get("side", "N/A")
            price = trade.get("price", 0)
            qty = trade.get("quantity", trade.get("qty", 0))

            record = (
                f"{str(timestamp):<10.10} {str(symbol):<10.10} "
                f"{str(side):<6.6} {str(price):>10.10} {str(qty):>8.8}"
            )
        else:
            record = str(trade)

        self.recent_trades.append(record)

    def get_key(self):
        # Read a key without blocking the dashboard
        return self.stdscr.getch()


def main(stdscr):
    # Run the dashboard UI loop
    dashboard = CursesDashboard(stdscr)
    dashboard.update(status="RUNNING")

    while True:
        dashboard.refresh()
        key = dashboard.get_key()

        if key in (ord("q"), ord("Q"), 3):
            break
        elif key in (ord("r"), ord("R")):
            dashboard.refresh()

        time.sleep(0.1)


if __name__ == "__main__":
    curses.wrapper(main)
