# stocksTUI

A fast, minimalist terminal app for checking stock prices, crypto, news, and historical charts — without leaving your shell. Built with [Textual](https://github.com/textualize/textual), powered by [yfinance](https://github.com/ranaroussi/yfinance), and made for people who prefer the command line over CNBC.

![stocksTUI Screenshot](https://raw.githubusercontent.com/andriy-git/stocksTUI/main/assets/screenshot.png)

---

## ✨ Features

*   **Live-ish Price Data**
    Watch your favorite tickers update in near real-time with configurable refresh intervals.

*   **Watchlists That Make Sense**
    Organize your assets into lists like "Tech", "Crypto", "Dividend Traps", or "Memes". Manage them entirely from the UI — no need to touch JSON unless you want to.

*   **Tag-Based Filtering**
    Assign tags (e.g., `growth`, `ev`, `semiconductor`) to your tickers and instantly filter any watchlist to see only what's relevant.

*   **Charts & Tables, Your Way**
    View historical performance from `1D` to `Max`, from a table or a chart.

*   **News That Matters**
    See the latest headlines per ticker or a combined feed — no ads, no autoplay videos, just info.

*   **Keyboard-Friendly, Mouse-Optional**
    Navigate everything with Vim-style keys or arrow keys. Bonus: lots of helpful keybindings, fully documented.

*   **Custom Themes & Settings**
    Tweak the look and feel with built-in themes or your own. Set your default tab, hide unused ones, and make it feel like *your* dashboard.

*   **Smart Caching**
    The app remembers what it can. Market-aware caching keeps startup fast and avoids pointless API calls on weekends or holidays.

> ⚠️ Note: All symbols follow [Yahoo Finance](https://finance.yahoo.com/) format — e.g., `AAPL` for Apple, `^GSPC` for S\&P 500, and `BTC-USD` for Bitcoin.

---

## 🛠 Requirements

*   **Python** 3.9 or newer
*   **OS Support:**

    *   **Linux / macOS** — Fully supported
    *   **Windows** — Use **Windows Terminal** with **WSL2**. It *won’t* work in the old `cmd.exe`.

---

## 🚀 Installation

The easiest way to install is with [`pipx`](https://pypa.github.io/pipx/):

### 1. Install pipx (if you don’t already have it):

```bash
# Debian/Ubuntu
sudo apt install pipx

# Arch Linux
sudo pacman -S python-pipx

# macOS
brew install pipx

# Or fallback to pip
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

### 2. Install stocksTUI:

```bash
pipx install stocksTUI
```

Done. You can now run `stockstui` from anywhere.

---

## 🧭 Usage

Run the app like so:

```bash
stockstui
```

Need help?

```bash
stockstui -h          # Short help  
stockstui --man       # Full user manual  
```

---

### 💡 Command-Line Examples

```bash
stockstui --history TSLA
```

Open on Tesla's History tab.

```bash
stockstui --news "NVDA,AMD"
```

Get combined news for NVIDIA and AMD.

```bash
stockstui --session-list "EV Stocks=TSLA,RIVN,LCID"
```

Create a temporary watchlist for this session only.

```bash
stockstui --history TSLA --period 5d --chart
```

Launch a 5-day chart for Tesla.

---

## ⌨️ Keybindings

*   Press `?` inside the app for a quick keybinding cheat sheet
*   Run `stockstui --man` for the full breakdown

---

## 🧑‍💻 For Developers: Install from Source

Want to try the bleeding-edge version or contribute?

```bash
git clone https://github.com/andriy-git/stocksTUI.git
cd stocksTUI
./install.sh
```

This sets up a virtual environment and a global `stockstui` command so you can test and develop from anywhere.

---

## ⚖️ License

Licensed under the **GNU GPL v3.0**.
See `LICENSE` for the legalese.
