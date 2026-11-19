"""
Crypto Intelligence Agent — terminal user interface.

A clean, opencode-inspired layout:

    ┌ sidebar ─┐ ┌────────────── chat ──────────────┐
    │ sessions │ │  conversation, streamed live     │
    │ skills   │ │                                  │
    │          │ ├──────────────────────────────────┤
    │          │ │  composer (always visible)       │
    └──────────┘ └──────────────────────────────────┘

The composer keeps focus at all times. Enter sends, Ctrl+J inserts a
newline, Ctrl+Up / Ctrl+Down walk the input history, Tab completes a
slash command, Ctrl+P opens the command palette.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Group
from rich.text import Text

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

# Project root on sys.path so this module can be launched directly.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.agent import CryptoIntelligenceAgent  # noqa: E402
from core.conversation import get_conversation_manager  # noqa: E402
from core.skill_registry import get_skill_registry  # noqa: E402
from database.storage import get_db_manager  # noqa: E402


# ============================================================
# Palette commands
# ============================================================

COMMANDS: List[tuple[str, str]] = [
    ("/help", "Show every command"),
    ("/status", "Agent, market and chain status"),
    ("/scan top", "Top coins by market cap"),
    ("/scan breadth", "Market breadth and regime"),
    ("/scan momentum", "Momentum leaders"),
    ("/scan sectors", "Sector rotation"),
    ("/scan newpairs", "New DEX pools"),
    ("/analyze", "Full analysis for a symbol"),
    ("/compare", "Compare two symbols"),
    ("/derivs", "Funding, open interest, long/short"),
    ("/correlation", "Correlation matrix and BTC beta"),
    ("/orderbook", "Order book depth and walls"),
    ("/fib", "Fibonacci retracement levels"),
    ("/profile", "Volume profile (POC, value area)"),
    ("/volatility", "Realised volatility and regime"),
    ("/reversion", "Mean-reversion z-score"),
    ("/ichimoku", "Ichimoku cloud"),
    ("/wyckoff", "Wyckoff phase"),
    ("/gas", "Gas prices across chains"),
    ("/paper create", "Open a paper-trading account"),
    ("/paper list", "List paper accounts"),
    ("/paper open", "Open a paper position"),
    ("/paper close", "Close a paper position"),
    ("/paper stats", "Paper account performance"),
    ("/strategy create", "Create a strategy"),
    ("/strategy list", "List strategies"),
    ("/strategy backtest", "Backtest a strategy"),
    ("/strategy optimize", "Grid-search parameters"),
    ("/strategy learn", "Discover patterns in history"),
    ("/journal add", "Log a trade"),
    ("/journal list", "List journal trades"),
    ("/journal stats", "Journal statistics"),
    ("/watchlist", "Manage the watchlist"),
    ("/skills", "Enable or disable skills"),
    ("/report", "Generate a research report"),
    ("/config", "Inspect configuration"),
    ("/copy", "Copy the last agent response"),
]

ROLE_STYLE = {
    "user": ("YOU", "#58a6ff"),
    "assistant": ("AGENT", "#3fb950"),
    "system": ("SYSTEM", "#8b949e"),
    "error": ("ERROR", "#f85149"),
}


# ============================================================
# Widgets
# ============================================================

class ChatEntry(Static):
    """One message in the transcript, with a role header."""

    def __init__(self, role: str, body: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.role = role
        self.body = body
        self.stamp = datetime.now().strftime("%H:%M")
        self._paint()

    def set_body(self, body: str) -> None:
        self.body = body
        self._paint()

    def _paint(self) -> None:
        label, colour = ROLE_STYLE.get(self.role, (self.role.upper(), "#8b949e"))
        header = Text()
        header.append(label, style=f"bold {colour}")
        header.append("   " + self.stamp, style="#6e7681")
        body = Text(self.body, style="#c9d1d9")
        self.update(Group(header, body))


class Prompt(TextArea):
    """Composer. Enter sends, Ctrl+J adds a newline, history on Ctrl+Up/Down."""

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            super().__init__()
            self.value = value

    class Complete(Message):
        pass

    BINDINGS = [
        Binding("enter", "submit", "Send", show=False, priority=True),
        Binding("ctrl+j", "newline", "Newline", show=False, priority=True),
        Binding("ctrl+up", "history_prev", "History", show=False, priority=True),
        Binding("ctrl+down", "history_next", "History", show=False, priority=True),
        Binding("tab", "complete", "Complete", show=False, priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.input_history: List[str] = []
        self.history_index = 0

    def action_submit(self) -> None:
        text = self.text.strip()
        if not text:
            return
        self.input_history.append(text)
        self.history_index = len(self.input_history)
        self.text = ""
        self.post_message(self.Submitted(text))

    def action_newline(self) -> None:
        self.insert("\n")

    def action_history_prev(self) -> None:
        if not self.input_history:
            return
        self.history_index = max(0, self.history_index - 1)
        self.text = self.input_history[self.history_index]
        self.cursor_position = len(self.text)

    def action_history_next(self) -> None:
        if not self.input_history:
            return
        if self.history_index >= len(self.input_history) - 1:
            self.history_index = len(self.input_history)
            self.text = ""
        else:
            self.history_index += 1
            self.text = self.input_history[self.history_index]
            self.cursor_position = len(self.text)

    def action_complete(self) -> None:
        self.post_message(self.Complete())


class CommandPalette(ModalScreen[Optional[str]]):
    """Fuzzy command list. Dismisses with the chosen command string."""

    BINDINGS = [Binding("escape", "cancel", "Close", show=False)]

    def compose(self) -> ComposeResult:
        yield Container(
            Input(placeholder="Search commands…", id="palette-input"),
            OptionList(id="palette-list"),
            Static("Enter to insert  ·  Esc to close", id="palette-help"),
            id="palette-box",
        )

    async def on_mount(self) -> None:
        self._fill("")
        self.query_one("#palette-input", Input).focus()

    def _fill(self, query: str) -> None:
        options = self.query_one("#palette-list", OptionList)
        options.clear_options()
        q = query.strip().lower()
        for name, desc in COMMANDS:
            if q and q not in name.lower() and q not in desc.lower():
                continue
            options.add_option(Option(f"{name:<22} {desc}", id=name))
        if options.option_count:
            options.highlighted = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        self._fill(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        options = self.query_one("#palette-list", OptionList)
        if options.option_count:
            self.dismiss(options.get_option_at_index(options.highlighted or 0).id)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss(None)


class HelpScreen(ModalScreen[None]):
    """Keyboard and command reference."""

    BINDINGS = [Binding("escape", "close", "Close", show=False)]

    HELP = """\
[crypto-agent]

Composer
  Enter              send the message
  Ctrl+J             insert a newline
  Ctrl+Up / Down     walk input history
  Tab                complete a slash command
  Ctrl+C             copy the last response

Global
  Ctrl+P             command palette
  Ctrl+N             new session
  Ctrl+L             clear the transcript
  Ctrl+B             toggle the sidebar
  Ctrl+U / Ctrl+D    scroll the transcript
  F1                 this help
  Esc                return to the composer
  Ctrl+Q             quit

Anything you type is handled autonomously: slash commands run directly,
plain English is planned, executed and summarised. Try:

  "analyze SOL, then compare it with AVAX"
  "find momentum leaders and check the order book of the top one"
  "create a trend-following strategy for BTC, backtest it and report"
  "open a paper account with 10000 and buy 0.5 ETH"

Type /help in the composer for the full command list.
"""

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self.HELP, markup=True, id="help-text"),
            Static("Esc to close", id="help-footer"),
            id="help-box",
        )

    def action_close(self) -> None:
        self.dismiss(None)


# ============================================================
# Application
# ============================================================

class CryptoAgentTUI(App):
    """Full-screen terminal client for the crypto agent."""

    TITLE = "crypto-agent"

    CSS = """
    Screen {
        background: #0b0f14;
        color: #c9d1d9;
    }

    #titlebar {
        height: 1;
        background: #0d1117;
        color: #8b949e;
        padding: 0 2;
    }

    #body {
        height: 1fr;
    }

    /* ---------------- sidebar ---------------- */

    #sidebar {
        width: 32;
        background: #0d1117;
        border-right: solid #21262d;
        padding: 1 1 0 1;
    }

    #sidebar.hidden {
        display: none;
    }

    #brand {
        height: 1;
        color: #e6edf3;
        text-style: bold;
    }

    #brand-sub {
        height: 1;
        color: #6e7681;
        margin-bottom: 1;
    }

    .section {
        height: 1;
        color: #6e7681;
        text-style: bold;
        margin-top: 1;
    }

    #sessions {
        height: 12;
        background: #0d1117;
        border: none;
        padding: 0;
    }

    #sessions > .option-list--option {
        padding: 0;
        color: #c9d1d9;
    }

    #sessions > .option-list--option-highlighted {
        background: #1f6feb;
        color: #ffffff;
    }

    #skills {
        height: 1fr;
        background: #0d1117;
        padding: 0;
        scrollbar-size: 0 0;
    }

    .skill-line {
        height: 1;
        color: #8b949e;
    }

    /* ---------------- main ---------------- */

    #main {
        width: 1fr;
    }

    #chat {
        height: 1fr;
        padding: 1 2 0 2;
        background: #0b0f14;
        scrollbar-size-vertical: 1;
    }

    ChatEntry {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }

    #suggestions {
        height: auto;
        max-height: 2;
        padding: 0 2;
        color: #6e7681;
    }

    #composer {
        height: auto;
        padding: 1 2;
        background: #0d1117;
        border-top: solid #21262d;
    }

    #prompt {
        height: 6;
        background: #161b22;
        border: tall #30363d;
        padding: 0 1;
    }

    #prompt:focus {
        border: tall #58a6ff;
    }

    #hint {
        height: 1;
        color: #6e7681;
        padding: 0 1;
    }

    #status {
        height: 1;
        background: #0d1117;
        color: #8b949e;
        padding: 0 2;
    }

    /* ---------------- palette ---------------- */

    CommandPalette {
        align: center middle;
    }

    #palette-box {
        width: 78;
        height: auto;
        max-height: 80%;
        background: #0d1117;
        border: tall #30363d;
        padding: 1;
    }

    #palette-input {
        background: #161b22;
        border: tall #30363d;
    }

    #palette-input:focus {
        border: tall #58a6ff;
    }

    #palette-list {
        height: auto;
        max-height: 20;
        margin-top: 1;
        background: #0d1117;
        border: none;
    }

    #palette-help {
        height: 1;
        color: #6e7681;
        margin-top: 1;
    }

    /* ---------------- help ---------------- */

    HelpScreen {
        align: center middle;
    }

    #help-box {
        width: 78;
        height: auto;
        max-height: 85%;
        background: #0d1117;
        border: tall #30363d;
        padding: 1 2;
    }

    #help-text {
        height: auto;
        color: #c9d1d9;
    }

    #help-footer {
        height: 1;
        color: #6e7681;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "palette", "Commands", priority=True),
        Binding("ctrl+n", "new_session", "New session", priority=True),
        Binding("ctrl+l", "clear_chat", "Clear", priority=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", priority=True),
        Binding("ctrl+u", "scroll_up", "Scroll up", show=False, priority=True),
        Binding("ctrl+d", "scroll_down", "Scroll down", show=False, priority=True),
        Binding("f1", "help", "Help", priority=True),
        Binding("escape", "focus_prompt", "Composer", show=False),
        Binding("ctrl+c", "copy_chat", "Copy last response", show=False, priority=True),
        Binding("ctrl+q", "quit", "Quit", priority=True),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.agent: Optional[CryptoIntelligenceAgent] = None
        self.ready = False
        self.busy = False
        self.pending: List[str] = []
        self.session_label = "starting"

    # ---------------- composition ----------------

    def compose(self) -> ComposeResult:
        yield Static("", id="titlebar")
        yield Horizontal(
            Vertical(
                Static("crypto-agent", id="brand"),
                Static("autonomous research · paper trading", id="brand-sub"),
                Static("SESSIONS", classes="section"),
                OptionList(id="sessions"),
                Static("SKILLS", classes="section"),
                VerticalScroll(id="skills"),
                id="sidebar",
            ),
            Vertical(
                VerticalScroll(id="chat"),
                Static("", id="suggestions"),
                Container(
                    Prompt(
                        id="prompt",
                        placeholder="Ask anything, or type / for a command…",
                    ),
                    Static(
                        "Enter send  ·  Ctrl+J newline  ·  Tab complete  ·  "
                        "Ctrl+P commands  ·  Ctrl+C copy  ·  F1 help",
                        id="hint",
                    ),
                    id="composer",
                ),
                Static("", id="status"),
                id="main",
            ),
            id="body",
        )

    async def on_mount(self) -> None:
        self.query_one(Prompt).focus()
        self._render_titlebar()
        self._render_status()
        self._render_skills()
        self._write(
            "system",
            "Starting up — connecting to market data, chains and skills. "
            "The composer is ready; messages are queued until the agent is up.",
        )
        self.set_interval(1.0, self._render_titlebar)
        self.set_interval(5.0, self._render_status)
        self.run_worker(self._start_agent(), name="agent-init", exclusive=True)

    async def on_unmount(self) -> None:
        """Close provider sessions so the process can exit cleanly."""
        try:
            if self.agent is not None:
                await self.agent.shutdown()
        except Exception:
            pass

    # ---------------- agent lifecycle ----------------

    async def _start_agent(self) -> None:
        try:
            agent = CryptoIntelligenceAgent()
            ok = await agent.initialize()
            if not ok:
                self._write("error", "Agent failed to initialise. Check config/api_keys.env.")
                return
            self.agent = agent
            self.ready = True
            session_id = agent.status.current_session or ""
            self.session_label = session_id[:8] or "new"
            await self._refresh_sessions()
            self._render_status()
            self._write(
                "assistant",
                "Ready. I can scan the market, analyse coins, test strategies on a "
                "paper account, and keep a persistent journal. Try “analyze SOL”.",
            )
            while self.pending:
                await self._run_request(self.pending.pop(0))
        except Exception as exc:  # pragma: no cover - startup guard
            self._write("error", f"Startup error: {exc}")

    # ---------------- rendering helpers ----------------

    def _write(self, role: str, body: str) -> ChatEntry:
        chat = self.query_one("#chat", VerticalScroll)
        entry = ChatEntry(role, body)
        chat.mount(entry)
        # Bound transcript size so very long sessions stay responsive.
        entries = chat.query(ChatEntry)
        if len(entries) > 300:
            for old in entries[:100]:
                old.remove()
        self.call_after_refresh(self._scroll_chat)
        return entry

    def _scroll_chat(self) -> None:
        try:
            self.query_one("#chat", VerticalScroll).scroll_end(animate=False)
        except Exception:
            pass

    def _render_titlebar(self) -> None:
        bar = self.query_one("#titlebar", Static)
        text = Text()
        text.append("crypto-agent", style="bold #e6edf3")
        text.append("   ·   ", style="#30363d")
        text.append("autonomous crypto research", style="#8b949e")
        text.append(" " * 4)
        text.append(datetime.now().strftime("%H:%M:%S"), style="#6e7681")
        bar.update(text)

    def _render_status(self) -> None:
        status = self.query_one("#status", Static)
        text = Text()
        if not self.agent:
            text.append("● ", style="#d29922")
            text.append("initialising agent…", style="#8b949e")
            status.update(text)
            return
        s = self.agent.status
        for label, ok in (
            ("market", s.market_data_connected),
            ("ai", s.kilo_connected),
            ("chain", s.blockchain_connected),
        ):
            text.append("● ", style="#3fb950" if ok else "#f85149")
            text.append(f"{label}  ", style="#8b949e")
        text.append("◆ ", style="#58a6ff")
        text.append(f"skills {s.active_skills}/{s.total_skills}  ", style="#8b949e")
        text.append("◆ ", style="#58a6ff")
        text.append(f"session {self.session_label}  ", style="#8b949e")
        text.append("◆ ", style="#58a6ff")
        text.append(s.current_model, style="#8b949e")
        if self.busy:
            text.append("   working…", style="#d29922")
        status.update(text)

    def _render_skills(self) -> None:
        box = self.query_one("#skills", VerticalScroll)
        box.remove_children()
        try:
            skills = get_skill_registry().list_skills()
        except Exception:
            skills = []
        active = sum(1 for s in skills if getattr(s.status, "value", "") == "active")
        box.mount(Static(f"{active} active of {len(skills)}", classes="skill-line"))
        for skill in skills[:60]:
            state = getattr(skill.status, "value", "inactive")
            dot = "●" if state == "active" else ("▲" if state == "error" else "○")
            colour = "#3fb950" if state == "active" else ("#f85149" if state == "error" else "#484f58")
            line = Text()
            line.append(dot + " ", style=colour)
            line.append(skill.name, style="#8b949e" if state != "active" else "#c9d1d9")
            box.mount(Static(line, classes="skill-line"))

    async def _refresh_sessions(self) -> None:
        try:
            db = await get_db_manager()
            rows = await db.list_sessions(limit=40)
        except Exception:
            return
        options = self.query_one("#sessions", OptionList)
        options.clear_options()
        current = get_conversation_manager().get_session_info() or {}
        current_id = current.get("session_id") or self.agent.status.current_session
        index = 0
        for i, row in enumerate(rows):
            title = (row.title or "session").strip()
            if len(title) > 24:
                title = title[:23] + "…"
            stamp = row.updated_at.strftime("%m/%d %H:%M") if row.updated_at else ""
            marker = "▸ " if row.session_id == current_id else "  "
            options.add_option(Option(f"{marker}{title}  {stamp}", id=row.session_id))
            if row.session_id == current_id:
                index = i
        if options.option_count:
            options.highlighted = index

    def _update_suggestions(self, text: str) -> None:
        bar = self.query_one("#suggestions", Static)
        stripped = text.strip()
        if not stripped.startswith("/") or " " in stripped:
            bar.update("")
            return
        matches = [(n, d) for n, d in COMMANDS if n.startswith(stripped)]
        if not matches:
            bar.update(Text("no matching command — F1 for help", style="#6e7681"))
            return
        line = Text()
        for i, (name, desc) in enumerate(matches[:4]):
            if i:
                line.append("   ")
            line.append(name, style="#58a6ff")
            line.append(f" {desc}", style="#6e7681")
        bar.update(line)

    # ---------------- events ----------------

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        if event.text_area.id == "prompt":
            self._update_suggestions(event.text_area.text)

    async def on_prompt_submitted(self, event: Prompt.Submitted) -> None:
        text = event.value
        if text.lower() in ("/exit", "/quit"):
            self.exit()
            return
        if text.strip().lower() == "/copy":
            self.action_copy_chat()
            return
        if not self.ready or not self.agent:
            self._write("user", text)
            self.pending.append(text)
            self._write(
                "system",
                f"Queued ({len(self.pending)}). The agent finishes connecting in a "
                "moment, then your request runs automatically.",
            )
            return
        if self.busy:
            self.pending.append(text)
            self._write("system", f"Queued ({len(self.pending)}); the current request is still running.")
            return

        await self._run_request(text)

    async def _run_request(self, text: str) -> None:
        """Execute one user request and stream the answer into the transcript."""
        self.busy = True
        prompt = self.query_one(Prompt)
        prompt.disabled = True
        self._render_status()
        self._write("user", text)
        entry = self._write("assistant", "working…")

        buffer = ""
        try:
            async for chunk in self.agent.process_message(text):
                buffer += chunk
                entry.set_body(buffer)
                self.call_after_refresh(self._scroll_chat)
        except Exception as exc:
            entry.set_body(buffer + f"\n\n[error] {exc}")
        finally:
            if not buffer:
                entry.set_body("(no output — check logs with /status)")
            self.busy = False
            prompt.disabled = False
            prompt.focus()
            self._render_status()
            await self._maybe_title_session(text)
            await self._refresh_sessions()

    async def _maybe_title_session(self, text: str) -> None:
        """Give the current session a human title from its first request."""
        try:
            conversation = get_conversation_manager()
            info = conversation.get_session_info() or {}
            session_id = info.get("session_id")
            title = (info.get("title") or "").strip().lower()
            if not session_id or title not in ("", "new conversation", "untitled", "session"):
                return
            db = await get_db_manager()
            clean = " ".join(text.split())[:48]
            await db.update_session(session_id, title=clean)
        except Exception:
            pass

    def _complete_command(self) -> None:
        prompt = self.query_one(Prompt)
        text = prompt.text
        if not text.startswith("/"):
            return
        first = text.split(" ", 1)[0]
        matches = [name for name, _ in COMMANDS if name.startswith(first)]
        if not matches:
            return
        if len(matches) == 1:
            completed = matches[0]
        else:
            completed = os.path.commonprefix(matches).rstrip()
        if len(completed) > len(first):
            rest = text[len(first):]
            prompt.text = completed if rest.strip() else completed + " "
            prompt.cursor_position = len(prompt.text)
            self._update_suggestions(prompt.text)

    def on_prompt_complete(self, event: Prompt.Complete) -> None:
        event.stop()
        self._complete_command()

    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        if event.option_list.id != "sessions" or not event.option_id:
            return
        await self._load_session(event.option_id)

    async def _load_session(self, session_id: str) -> None:
        try:
            conversation = get_conversation_manager()
            session = await conversation.initialize(session_id)
            db = await get_db_manager()
            messages = await db.get_messages(session.id, limit=200)
        except Exception as exc:
            self._write("error", f"Could not load session: {exc}")
            return
        self.session_label = session.session_id[:8]
        self.query_one("#chat", VerticalScroll).remove_children()
        for message in messages:
            role = getattr(message.role, "value", message.role)
            role = role if role in ("user", "assistant", "system") else "system"
            self._write(role, message.content)
        if not messages:
            self._write("system", "This session has no messages yet.")
        self._render_status()
        await self._refresh_sessions()
        self.query_one(Prompt).focus()

    # ---------------- actions ----------------

    def action_palette(self) -> None:
        self.push_screen(CommandPalette(), self._apply_palette)

    def _apply_palette(self, command: Optional[str]) -> None:
        if not command:
            return
        prompt = self.query_one(Prompt)
        prompt.text = command + " "
        prompt.cursor_position = len(prompt.text)
        prompt.focus()
        self._update_suggestions(prompt.text)

    def action_new_session(self) -> None:
        self.run_worker(self._new_session(), name="new-session")

    async def _new_session(self) -> None:
        try:
            conversation = get_conversation_manager()
            session = await conversation.initialize()
        except Exception as exc:
            self._write("error", f"Could not create session: {exc}")
            return
        self.session_label = session.session_id[:8]
        self.query_one("#chat", VerticalScroll).remove_children()
        self._write("system", f"New session {self.session_label}. Context cleared.")
        await self._refresh_sessions()
        self._render_status()
        self.query_one(Prompt).focus()

    def action_clear_chat(self) -> None:
        self.query_one("#chat", VerticalScroll).remove_children()
        self._write("system", "Transcript cleared. Conversation context is unchanged.")
        self.query_one(Prompt).focus()

    def action_copy_chat(self) -> None:
        """Copy the latest chat text to the system clipboard.

        Prefers an active text selection; otherwise copies the most recent
        user/assistant transcript entry. Bound to Ctrl+C globally.
        """
        text = ""
        try:
            selection = self.screen.get_selected_text()
            if selection:
                text = selection.strip()
        except Exception:
            text = ""
        if not text:
            try:
                entries = list(self.query(ChatEntry))
                for entry in reversed(entries):
                    if entry.role in ("user", "assistant") and (entry.body or "").strip():
                        text = entry.body.strip()
                        break
            except Exception:
                text = ""
        if not text:
            self.notify("Nothing to copy yet", title="Copy")
            return
        try:
            self.copy_to_clipboard(text)
            self.notify("Copied to clipboard", title="Copy")
        except Exception:
            self.notify("Clipboard unavailable", title="Copy")

    def action_toggle_sidebar(self) -> None:
        self.query_one("#sidebar").toggle_class("hidden")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_prompt(self) -> None:
        self.query_one(Prompt).focus()

    def action_scroll_up(self) -> None:
        self.query_one("#chat", VerticalScroll).scroll_page_up(animate=False)

    def action_scroll_down(self) -> None:
        self.query_one("#chat", VerticalScroll).scroll_page_down(animate=False)


async def main() -> None:
    app = CryptoAgentTUI()
    await app.run_async()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
