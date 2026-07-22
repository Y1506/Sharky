import asyncio
import contextlib
import threading
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
import uvicorn

from .manager import DownloadManager
from .models import DownloadItem

# Global instance
manager: Optional[DownloadManager] = None

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global manager
    manager = DownloadManager()
    yield
    if manager:
        manager.stop_downloads()

app = FastAPI(title="Download Manager API", lifespan=lifespan)

class AddUrlRequest(BaseModel):
    url: str
    quality: str = "best"
    include_subtitles: bool = False
    embed_chapters: bool = False

@app.post("/api/downloads")
def add_download(req: AddUrlRequest):
    item_id = manager.add_url(
        url=req.url,
        quality=req.quality,
        include_subtitles=req.include_subtitles,
        embed_chapters=req.embed_chapters
    )
    if not item_id:
        raise HTTPException(status_code=400, detail="Failed to add download (invalid or already exists)")
    return {"id": item_id, "message": "Download added"}

@app.get("/api/downloads")
def list_downloads():
    try:
        items = manager.db.get_all_downloads()
        return [
            {
                "id": i.id,
                "url": i.url,
                "title": i.title,
                "status": i.status,
                "download_type": i.download_type,
                "download_speed": i.download_speed,
                "eta": i.eta,
                "error_message": i.error_message,
                "quality": i.quality,
            }
            for i in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/downloads/start")
def start_downloads():
    started = manager.start_downloads()
    return {"started": started}

@app.post("/api/downloads/pause")
def pause_downloads():
    manager.pause_downloads()
    return {"message": "Downloads paused"}

@app.post("/api/downloads/resume")
def resume_downloads():
    manager.resume_downloads()
    return {"message": "Downloads resumed"}

@app.post("/api/downloads/stop")
def stop_downloads():
    manager.stop_downloads()
    return {"message": "Downloads stopped"}

@app.post("/api/downloads/retry-failed")
def retry_failed():
    count = manager.retry_failed_downloads()
    return {"message": f"Reset {count} failed downloads"}

@app.delete("/api/downloads/completed")
def clear_completed():
    count = manager.clear_completed_downloads()
    return {"message": f"Cleared {count} completed downloads"}

@app.delete("/api/downloads/failed")
def clear_failed():
    count = manager.clear_failed_downloads()
    return {"message": f"Cleared {count} failed downloads"}

@app.delete("/api/downloads/{item_id}")
def remove_download(item_id: int):
    count = manager.remove_downloads([item_id])
    if count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Download removed"}

@app.get("/api/stats")
def get_stats():
    items = manager.db.get_all_downloads()
    total = len(items)
    pending = sum(1 for i in items if i.status == "pending")
    downloading = sum(1 for i in items if i.status == "downloading")
    completed = sum(1 for i in items if i.status == "completed")
    failed = sum(1 for i in items if i.status == "failed")
    paused = sum(1 for i in items if i.status == "paused")
    return {
        "total": total,
        "pending": pending,
        "downloading": downloading,
        "completed": completed,
        "failed": failed,
        "paused": paused,
        "is_running": manager.running,
        "is_paused": not manager.pause_event.is_set()
    }

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            items = manager.db.get_all_downloads()
            data = [
                {
                    "id": i.id,
                    "title": i.title,
                    "status": i.status,
                    "download_speed": i.download_speed,
                    "eta": i.eta,
                }
                for i in items
            ]
            await websocket.send_json({"downloads": data, "stats": get_stats()})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port)
