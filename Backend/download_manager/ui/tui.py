import os
import json
import asyncio
import httpx
import websockets
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, DataTable, Input, Static, Button, Label, Switch
from textual.reactive import reactive

API_URL = "http://127.0.0.1:8000/api"
WS_URL = "ws://127.0.0.1:8000/ws/progress"

TUI_CONFIG_PATH = Path.home() / ".config" / "sharky" / "tui_settings.json"

def load_local_tui_settings() -> dict:
    default_settings = {
        "dark_theme": True,
        "bell_on_completion": True,
    }
    try:
        if TUI_CONFIG_PATH.exists():
            with open(TUI_CONFIG_PATH, "r", encoding="utf-8") as f:
                return {**default_settings, **json.load(f)}
    except Exception:
        pass
    return default_settings

def save_local_tui_settings(data: dict):
    try:
        TUI_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TUI_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

class TuiSettingsModal(ModalScreen):
    """Modal screen for viewing and updating Centralized and Local TUI settings."""
    CSS = """
    TuiSettingsModal {
        align: center middle;
    }
    #dialog {
        width: 76;
        height: 28;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    .setting-row {
        height: 3;
        margin-bottom: 1;
        layout: horizontal;
    }
    .label {
        width: 32;
        content-align: left middle;
    }
    .field {
        width: 38;
    }
    #buttons {
        dock: bottom;
        height: 3;
        layout: horizontal;
        align: right middle;
    }
    """

    def __init__(self, client: httpx.AsyncClient, local_settings: dict, on_save_local):
        super().__init__()
        self.client = client
        self.local_settings = local_settings
        self.on_save_local = on_save_local
        self.central_settings = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("[bold cyan]Preferences & Configuration[/bold cyan]")
            yield Label("[dim]Centralized settings sync with Web UI; local settings apply to this terminal.[/dim]")
            
            with Horizontal(classes="setting-row"):
                yield Label("Default Path [bold blue][Engine][/bold blue]:", classes="label")
                yield Input(id="in-dir", classes="field")
            
            with Horizontal(classes="setting-row"):
                yield Label("Max Tasks (1..64) [bold blue][Engine][/bold blue]:", classes="label")
                yield Input(id="in-tasks", classes="field")

            with Horizontal(classes="setting-row"):
                yield Label("Speed Limit B/s [bold blue][Engine][/bold blue]:", classes="label")
                yield Input(id="in-speed", classes="field")

            with Horizontal(classes="setting-row"):
                yield Label("Proxy URL [bold blue][Engine][/bold blue]:", classes="label")
                yield Input(id="in-proxy", classes="field")

            with Horizontal(classes="setting-row"):
                yield Label("Bell on Done [bold magenta][Local][/bold magenta]:", classes="label")
                yield Switch(value=self.local_settings.get("bell_on_completion", True), id="sw-bell")

            with Horizontal(classes="setting-row"):
                yield Label("Dark Mode [bold magenta][Local][/bold magenta]:", classes="label")
                yield Switch(value=self.local_settings.get("dark_theme", True), id="sw-theme")

            with Horizontal(id="buttons"):
                yield Button("Cancel", id="btn-cancel", variant="default")
                yield Button("Save & Apply", id="btn-save", variant="primary")

    async def on_mount(self) -> None:
        try:
            resp = await self.client.get("/settings")
            if resp.status_code == 200:
                self.central_settings = resp.json()
                self.query_one("#in-dir", Input).value = str(self.central_settings.get("download_dir", ""))
                self.query_one("#in-tasks", Input).value = str(self.central_settings.get("concurrent_downloads", 5))
                self.query_one("#in-speed", Input).value = str(self.central_settings.get("download_speed_limit", 0))
                self.query_one("#in-proxy", Input).value = str(self.central_settings.get("proxy_url", ""))
        except Exception:
            pass

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
        elif event.button.id == "btn-save":
            # 1. Save Decentralized Local Settings
            sw_bell = self.query_one("#sw-bell", Switch).value
            sw_theme = self.query_one("#sw-theme", Switch).value
            self.local_settings["bell_on_completion"] = sw_bell
            self.local_settings["dark_theme"] = sw_theme
            self.on_save_local(self.local_settings)

            # 2. Save Centralized Engine Settings
            payload = {}
            new_dir = self.query_one("#in-dir", Input).value.strip()
            if new_dir:
                payload["download_dir"] = new_dir
            new_tasks = self.query_one("#in-tasks", Input).value.strip()
            if new_tasks.isdigit():
                payload["concurrent_downloads"] = int(new_tasks)
            new_speed = self.query_one("#in-speed", Input).value.strip()
            if new_speed.isdigit():
                payload["download_speed_limit"] = int(new_speed)
            new_proxy = self.query_one("#in-proxy", Input).value.strip()
            payload["proxy_url"] = new_proxy
            payload["proxy_enabled"] = bool(new_proxy)

            try:
                await self.client.put("/settings", json=payload)
            except Exception:
                pass

            self.dismiss()

class StatsBar(Static):
    stats = reactive({"total": 0, "pending": 0, "downloading": 0, "completed": 0, "failed": 0, "paused": 0})

    def render(self) -> str:
        s = self.stats
        return f"Total: {s.get('total', 0)} | Pending: {s.get('pending', 0)} | Downloading: {s.get('downloading', 0)} | Completed: {s.get('completed', 0)} | Failed: {s.get('failed', 0)} | Paused: {s.get('paused', 0)}"

class DownloadTUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #stats-bar {
        dock: top;
        height: 1;
        background: $primary;
        color: $text;
        text-align: center;
    }
    DataTable {
        height: 1fr;
    }
    #input-container {
        dock: bottom;
        height: 3;
        layout: horizontal;
    }
    Input {
        width: 1fr;
    }
    Button {
        width: 15;
    }
    """
    
    BINDINGS = [
        ("c", "settings", "Settings"),
        ("s", "start", "Start All"),
        ("p", "pause", "Pause All"),
        ("r", "resume", "Resume All"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.local_settings = load_local_tui_settings()
        self.known_completed = set()
        self.initial_load_done = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatsBar(id="stats-bar")
        yield DataTable(id="download-table")
        with Container(id="input-container"):
            yield Input(placeholder="Enter URL to download...", id="url-input")
            yield Button("Add", id="add-btn", variant="primary")
        yield Footer()

    async def on_mount(self) -> None:
        self.dark = self.local_settings.get("dark_theme", True)
        self.table = self.query_one(DataTable)
        self.table.add_columns("ID", "Title", "Status", "Speed", "ETA")
        self.table.cursor_type = "row"
        self.client = httpx.AsyncClient(base_url=API_URL)
        
        # Start websocket background task
        self.ws_task = asyncio.create_task(self.poll_websocket())

    def apply_local_settings(self, new_settings: dict):
        self.local_settings = new_settings
        save_local_tui_settings(new_settings)
        self.dark = new_settings.get("dark_theme", True)

    def action_settings(self):
        self.push_screen(TuiSettingsModal(self.client, self.local_settings, self.apply_local_settings))

    async def poll_websocket(self):
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        self.update_ui(data)
            except Exception:
                await asyncio.sleep(2)

    def update_ui(self, data):
        # Update stats
        stats_bar = self.query_one(StatsBar)
        stats_bar.stats = data.get("stats", {})

        # Update table
        downloads = data.get("downloads", [])
        
        current_keys = [k.value for k in self.table.rows.keys()]
        updated_keys = set()
        
        for d in downloads:
            row_key = str(d["id"])
            updated_keys.add(row_key)
            speed = d.get("download_speed") or ""
            eta = d.get("eta") or ""
            status = d["status"]
            title = d["title"]
            if len(title) > 50:
                title = title[:47] + "..."
            
            row_data = (str(d["id"]), title, status, speed, eta)
            
            if row_key in current_keys:
                self.table.update_row(row_key, *row_data)
            else:
                self.table.add_row(*row_data, key=row_key)

            # Check completion for terminal bell alert
            if status == "completed":
                if row_key not in self.known_completed:
                    self.known_completed.add(row_key)
                    if self.initial_load_done and self.local_settings.get("bell_on_completion", True):
                        print("\a", end="", flush=True)

        self.initial_load_done = True
                
        # Remove deleted
        for k in current_keys:
            if k not in updated_keys:
                self.table.remove_row(k)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-btn":
            await self.add_url()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "url-input":
            await self.add_url()

    async def add_url(self):
        inp = self.query_one(Input)
        url = inp.value.strip()
        if not url:
            return
        inp.value = ""
        try:
            await self.client.post("/downloads", json={
                "url": url,
                "quality": "best",
                "include_subtitles": True,
                "embed_chapters": True
            })
        except Exception:
            pass

    async def action_pause(self):
        try:
            await self.client.post("/downloads/pause")
        except Exception:
            pass

    async def action_resume(self):
        try:
            await self.client.post("/downloads/resume")
        except Exception:
            pass

    async def action_start(self):
        try:
            await self.client.post("/downloads/start")
        except Exception:
            pass

    async def on_unmount(self):
        self.ws_task.cancel()
        await self.client.aclose()

if __name__ == "__main__":
    app = DownloadTUI()
    app.run()
