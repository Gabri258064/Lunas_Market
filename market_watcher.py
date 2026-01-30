import os
import sys
import time
import json
import yfinance as yf
import datetime
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.align import Align
from rich.prompt import Prompt

# -----------------------------------------------------------------------------
# LUNAS MARKET v1.0 - Institutional Grade Asset Tracker
# -----------------------------------------------------------------------------
# Author      : Gabri2580 & Project Lunas
# License     : MIT
# Description : Pro Dashboard with Multi-Timeframe, Favorites & Asset Types.
# -----------------------------------------------------------------------------

# --- CONFIGURATION ---
CONFIG_FILE = "market_config.json"
REFRESH_SECONDS = 300  # 5 Minutes

# Initial Default State
DEFAULT_CONFIG = {
    "assets": ["BTC-USD", "ETH-USD", "NVDA", "TSLA", "AAPL", "EURUSD=X"],
    "favorites": ["BTC-USD"],
    "timeframe": "DAY"  # Options: DAY, WEEK, MONTH
}

# --- THEME (Lunas Cyberpunk) ---
C_PRIMARY = "bold #8c00be"  # Lunas Purple
C_ACCENT  = "#00f5d4"       # Neon Cyan
C_UP      = "#00ff00"       # Matrix Green
C_DOWN    = "#ff0055"       # Cyber Red
C_TEXT    = "white"
C_FAV     = "gold1"         # Gold for stars

console = Console()

# --- LUNAS ASCII LOGO ---
LUNAS_LOGO = """
===============================================================
    ★     ██╗      ██╗   ██╗ ███╗   ██╗  █████╗  ███████╗    ★
  ☾       ██║ .    ██║   ██║ ████╗  ██║ ██╔══██╗ ██╔════╝ .
       .  ██║      ██║ + ██║ ██╔██╗ ██║ ███████║ ███████╗    ☾
    ★     ██║   .  ██║   ██║ ██║╚██╗██║ ██╔══██║ ╚════██║       .
       .  ███████╗ ╚██████╔╝ ██║ ╚████║ ██║  ██║ ███████║  ★
    .     ╚══════╝  ╚═════╝  ╚═╝  ╚═══╝ ╚═╝  ╚═╝ ╚══════╝      ☽

===============================================================
"""

# --- DATA MANAGEMENT ---
def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            # Ensure all keys exist (migration fix)
            for k, v in DEFAULT_CONFIG.items():
                if k not in data:
                    data[k] = v
            return data
    except:
        return DEFAULT_CONFIG

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# --- ALGORITHMS & UTILS ---
def get_asset_icon(symbol):
    """Determines asset type based on ticker syntax."""
    if "-USD" in symbol or "-EUR" in symbol:
        return "🪙" # Crypto
    elif "=X" in symbol:
        return "💱" # Forex
    else:
        return "🏢" # Stock/ETF

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50.0
    deltas = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
    gains = [d for d in deltas if d > 0]
    losses = [-d for d in deltas if d < 0]
    avg_gain = sum(gains) / period if gains else 0
    avg_loss = sum(losses) / period if losses else 0
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_range_bar(low, high, current, width=15):
    if high == low: return "[gray]─[/]" * width
    position = (current - low) / (high - low)
    idx = int(position * (width - 1))
    idx = max(0, min(idx, width - 1))

    chars = ["─"] * width
    chars[idx] = "●"

    bar_str = ""
    for i, char in enumerate(chars):
        if i < idx: bar_str += f"[green]{char}[/]"
        elif i == idx: bar_str += f"[bold white]{char}[/]"
        else: bar_str += f"[red]{char}[/]"
    return bar_str

# --- CORE FETCHING ---
def fetch_data(config):
    watchlist = config["assets"]
    favorites = config["favorites"]
    timeframe = config["timeframe"]

    data = []
    if not watchlist: return []

    string_tickers = " ".join(watchlist)
    tickers = yf.Tickers(string_tickers)

    for symbol in watchlist:
        try:
            ticker = tickers.tickers[symbol]
            fast_info = ticker.fast_info

            current_price = fast_info.last_price
            prev_close = fast_info.previous_close
            change_pct = ((current_price - prev_close) / prev_close) * 100

            # Fetch History for RSI and Timeframe High/Low
            hist = ticker.history(period="1mo")
            closes = hist['Close'].tolist()
            highs = hist['High'].tolist()
            lows = hist['Low'].tolist()

            # Logic for Dynamic Timeframe
            if timeframe == "DAY":
                t_high = fast_info.day_high
                t_low = fast_info.day_low
            elif timeframe == "WEEK":
                # Last 5 days
                t_high = max(highs[-5:]) if len(highs) >= 5 else max(highs)
                t_low = min(lows[-5:]) if len(lows) >= 5 else min(lows)
            else: # MONTH
                t_high = max(highs)
                t_low = min(lows)

            rsi_val = calculate_rsi(closes)

            is_fav = symbol in favorites

            data.append({
                "symbol": symbol,
                "price": current_price,
                "change_pct": change_pct,
                "high": t_high,
                "low": t_low,
                "rsi": rsi_val,
                "is_fav": is_fav,
                "icon": get_asset_icon(symbol)
            })
        except Exception:
            # Error handling
            data.append({
                "symbol": symbol, "price": 0.0, "change_pct": 0.0,
                "high": 0.0, "low": 0.0, "rsi": 50.0,
                "is_fav": symbol in favorites, "icon": "?"
            })

    # SORTING: Favorites first, then Alphabetical
    data.sort(key=lambda x: (not x['is_fav'], x['symbol']))
    return data

# --- UI GENERATION ---
def generate_table(config):
    tf_label = config["timeframe"]
    table = Table(title="", expand=True, border_style="blue", header_style="bold white")

    table.add_column("Asset", style="bold cyan", no_wrap=True)
    table.add_column("Price", justify="right", style="bold white")
    table.add_column("24h %", justify="right")
    table.add_column(f"{tf_label} Range (L ↔ H)", justify="center")
    table.add_column("RSI (14)", justify="center")
    table.add_column("Signal", justify="center")

    market_data = fetch_data(config)

    for item in market_data:
        # Asset Name formatting
        fav_mark = f"[{C_FAV}]★[/] " if item['is_fav'] else "  "
        name_display = f"{item['icon']}  {fav_mark}{item['symbol']}"

        # Color Logic
        if item['change_pct'] >= 0:
            pct_str = f"[{C_UP}]▲ {item['change_pct']:+.2f}%[/]"
        else:
            pct_str = f"[{C_DOWN}]▼ {item['change_pct']:+.2f}%[/]"

        range_vis = get_range_bar(item['low'], item['high'], item['price'])

        # RSI Logic
        rsi = item['rsi']
        if rsi >= 70:
            rsi_str = f"[bold red]{rsi:.0f}[/]"
            status = "[red]OVERBOUGHT[/]"
        elif rsi <= 30:
            rsi_str = f"[bold green]{rsi:.0f}[/]"
            status = "[green]OVERSOLD[/]"
        else:
            rsi_str = f"[gray]{rsi:.0f}[/]"
            status = "[dim]NEUTRAL[/]"

        table.add_row(name_display, f"${item['price']:,.2f}", pct_str, range_vis, rsi_str, status)

    return table

def get_header():
    now = datetime.datetime.now().strftime("%H:%M:%S")
    # Updated with the new ASCII Logo
    return Panel(
        Align.center(
            f"[{C_PRIMARY}]{LUNAS_LOGO}[/]\n"
            f"[{C_PRIMARY}]-$-L U N A S   M A R K E T   W A T C H E R-$-[/]\n"
            f"[dim]Real-time Institutional Feed • Last Update: {now}[/]\n"
            f"[dim]Made by Gabri2580 & Project Lunas[/]"
        ),
        border_style=C_PRIMARY
    )

def get_footer():
    return Align.center(f"\n[black on {C_ACCENT}]  PRESS CTRL+C TO OPEN MANAGER MENU  [/]")

# --- MANAGER MENU ---
def show_manager(config, live_display):
    """Shows options with a clean screen."""
    # 1. Stop the Live update loop
    live_display.stop()

    # 2. Force Clear Screen (Clean slate)
    os.system('cls' if os.name == 'nt' else 'clear')

    # 3. Print Logo and Menu
    console.print(f"[{C_PRIMARY}]{LUNAS_LOGO}[/]")
    console.print(f"\n[{C_PRIMARY}]--- MANAGER MODE ---[/]")
    console.print(f"[1] Add Asset")
    console.print(f"[2] Remove Asset")
    console.print(f"[3] Toggle Favorite (★)")
    console.print(f"[4] Switch Timeframe (Current: [bold]{config['timeframe']}[/])")
    console.print(f"[5] Resume Monitoring")
    console.print(f"[0] Exit")

    choice = Prompt.ask("\nSelect Option", choices=["1", "2", "3", "4", "5", "0"], default="5")

    if choice == "1":
        new = Prompt.ask("Enter Symbol (e.g. NVDA, BTC-USD)").upper().strip()
        if new and new not in config["assets"]:
            config["assets"].append(new)
            console.print(f"[green]Added {new}![/]")

    elif choice == "2":
        rem = Prompt.ask("Enter Symbol to remove").upper().strip()
        if rem in config["assets"]:
            config["assets"].remove(rem)
            console.print(f"[yellow]Removed {rem}![/]")

    elif choice == "3":
        fav = Prompt.ask("Enter Symbol to Toggle Favorite").upper().strip()
        if fav in config["assets"]:
            if fav in config["favorites"]:
                config["favorites"].remove(fav)
                console.print(f"[yellow]Removed {fav} from favorites.[/]")
            else:
                config["favorites"].append(fav)
                console.print(f"[gold1]Added {fav} to favorites![/]")

    elif choice == "4":
        modes = ["DAY", "WEEK", "MONTH"]
        current_idx = modes.index(config["timeframe"])
        next_idx = (current_idx + 1) % len(modes)
        config["timeframe"] = modes[next_idx]
        console.print(f"[cyan]Timeframe switched to {config['timeframe']}![/]")

    elif choice == "0":
        console.print("[bold white]Exiting...[/]")
        sys.exit()

    save_config(config)
    console.print("[dim]Resuming dashboard in 2s...[/]")
    time.sleep(2)

    # Clear again before restarting live view for a polished look
    os.system('cls' if os.name == 'nt' else 'clear')
    live_display.start() # Restart Live update

# --- MAIN LOOP ---
def main():
    config = load_config()

    # Live Display
    with Live(Layout(), refresh_per_second=1, screen=True) as live:
        while True:
            try:
                # 1. Update UI
                board = generate_table(config)

                layout = Layout()
                layout.split_column(
                    Layout(get_header(), size=16), # Increased size for the bigger logo
                    Layout(board),
                    Layout(get_footer(), size=2)
                )
                live.update(layout)

                # 2. Wait loop (catch Ctrl+C)
                for _ in range(REFRESH_SECONDS):
                    time.sleep(1)

            except KeyboardInterrupt:
                show_manager(config, live)

if __name__ == "__main__":
    main()
