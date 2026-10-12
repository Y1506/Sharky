import asyncio
import httpx
import websockets
import json
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, DataTable, Input, Static, Button
from textual.reactive import reactive

API_URL = "http://127.0.0.1:8000/api"
WS_URL = "ws://127.0.0.1:8000/ws/progress"

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
        ("q", "quit", "Quit"),
        ("p", "pause", "Pause All"),
        ("r", "resume", "Resume All"),
        ("s", "start", "Start/Process"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield StatsBar(id="stats-bar")
        yield DataTable(id="download-table")
        with Container(id="input-container"):
            yield Input(placeholder="Enter URL to download...", id="url-input")
            yield Button("Add", id="add-btn", variant="primary")
        yield Footer()

    async def on_mount(self) -> None:
        self.table = self.query_one(DataTable)
        self.table.add_columns("ID", "Title", "Status", "Speed", "ETA")
        self.table.cursor_type = "row"
        self.client = httpx.AsyncClient(base_url=API_URL)
        
        # Start websocket background task
        self.ws_task = asyncio.create_task(self.poll_websocket())

    async def poll_websocket(self):
        while True:
            try:
                async with websockets.connect(WS_URL) as ws:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        self.update_ui(data)
            except Exception as e:
                await asyncio.sleep(2)

    def update_ui(self, data):
        # Update stats
        stats_bar = self.query_one(StatsBar)
        stats_bar.stats = data.get("stats", {})

        # Update table
        downloads = data.get("downloads", [])
        
        # We need to refresh the table efficiently.
        current_keys = [k.value for k in self.table.rows.keys()]
        
        # Keep track of updated keys
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
            # Send default config (with subtitles and chapters True as requested before)
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
