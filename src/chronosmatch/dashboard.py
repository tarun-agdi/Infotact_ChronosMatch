import curses
import time


class CursesDashboard:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.orders = 0
        self.trades = 0
        self.status = "STARTING"
        self.start_time = time.time()
        self.recent_trades = []

        # Enable terminal colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)

        # Hide the cursor
        curses.curs_set(0)

    def draw_header(self):
        # Draw the dashboard title
        self.stdscr.addstr(
            0, 2, "CHRONOSMATCH - TRADING ENGINE",
            curses.color_pair(2) | curses.A_BOLD
        )
        self.stdscr.addstr(1, 2, "-" * 60)

    def draw_metrics(self):
        # Show pipeline statistics
        elapsed = max(time.time() - self.start_time, 0.001)
        rate = self.orders / elapsed

        self.stdscr.addstr(3, 2, "ENGINE STATUS")
        self.stdscr.addstr(
            4, 2, f"Status          : {self.status}",
            curses.color_pair(1)
        )
        self.stdscr.addstr(5, 2, f"Orders Processed: {self.orders}")
        self.stdscr.addstr(6, 2, f"Trades Executed : {self.trades}")
        self.stdscr.addstr(7, 2, f"Orders / Second : {rate:.2f}")

    def draw_trades(self):
        # Show the latest executed trades
        self.stdscr.addstr(9, 2, "RECENT TRADES", curses.A_BOLD)
        self.stdscr.addstr(10, 2, "-" * 60)
        self.stdscr.addstr(11, 2, "TRADE DETAILS")

        for index, trade in enumerate(self.recent_trades[-5:]):
            self.stdscr.addstr(12 + index, 2, str(trade)[:55])

    def draw_footer(self):
        # Show keyboard shortcuts
        height, _ = self.stdscr.getmaxyx()
        self.stdscr.addstr(
            height - 2, 2,
            "Q: Quit | R: Refresh",
            curses.color_pair(3)
        )

    def refresh(self):
        # Redraw the complete screen
        self.stdscr.erase()
        self.draw_header()
        self.draw_metrics()
        self.draw_trades()
        self.draw_footer()
        self.stdscr.refresh()

    def update(self, orders=None, trades=None, status=None):
        # Update only the supplied values
        if orders is not None:
            self.orders = orders
        if trades is not None:
            self.trades = trades
        if status is not None:
            self.status = status

        self.refresh()

    def add_trade(self, trade):
        # Keep only the latest trade records
        self.recent_trades.append(trade)
        self.recent_trades = self.recent_trades[-5:]
        self.refresh()

    def get_key(self):
        # Read keyboard input without blocking
        self.stdscr.nodelay(True)
        return self.stdscr.getch()


def main(stdscr):
    # Start a standalone dashboard preview
    curses.curs_set(0)
    dashboard = CursesDashboard(stdscr)
    dashboard.update(status="RUNNING")

    while True:
        key = dashboard.get_key()

        if key in (ord("q"), ord("Q")):
            break

        if key in (ord("r"), ord("R")):
            dashboard.refresh()

        time.sleep(0.1)


if __name__ == "__main__":
    curses.wrapper(main)