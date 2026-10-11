import asyncio
import contextlib
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
        manager.cleanup()

app = FastAPI(title="Download Manager API", lifespan=lifespan)

class AddUrlRequest(BaseModel):
    url: str
    quality: str = "best"
    include_subtitles: bool = False
    embed_chapters: bool = False
    expected_hash: Optional[str] = None
    hash_algorithm: Optional[str] = "sha256"

class BatchAddUrlRequest(BaseModel):
    urls: List[str]
    quality: str = "best"
    include_subtitles: bool = False
    embed_chapters: bool = False

@app.post("/api/downloads")
async def add_download(req: AddUrlRequest):
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    item_id = await asyncio.to_thread(
        manager.add_url,
        url=req.url,
        quality=req.quality,
        include_subtitles=req.include_subtitles,
        embed_chapters=req.embed_chapters,
        expected_hash=req.expected_hash,
        hash_algorithm=req.hash_algorithm,
    )
    if not item_id:
        raise HTTPException(status_code=400, detail="Failed to add download (invalid or already exists)")
    return {"id": item_id, "message": "Download added"}

@app.post("/api/downloads/batch")
async def add_batch_downloads(req: BatchAddUrlRequest):
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    stats = await asyncio.to_thread(
        manager.add_batch_urls,
        urls=req.urls,
        quality=req.quality,
        include_subtitles=req.include_subtitles,
        embed_chapters=req.embed_chapters,
    )
    return stats

@app.get("/api/downloads")
async def list_downloads():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    try:
        items = await asyncio.to_thread(manager.db.get_all_downloads)
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
                "expected_hash": i.expected_hash,
                "actual_hash": i.actual_hash,
                "hash_algorithm": i.hash_algorithm,
            }
            for i in items
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/downloads/start")
async def start_downloads():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    started = await asyncio.to_thread(manager.start_downloads)
    return {"started": started}

@app.post("/api/downloads/pause")
async def pause_downloads():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    await asyncio.to_thread(manager.pause_downloads)
    return {"message": "Downloads paused"}

@app.post("/api/downloads/resume")
async def resume_downloads():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    await asyncio.to_thread(manager.resume_downloads)
    return {"message": "Downloads resumed"}

@app.post("/api/downloads/stop")
async def stop_downloads():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    await asyncio.to_thread(manager.stop_downloads)
    return {"message": "Downloads stopped"}

@app.post("/api/downloads/retry-failed")
async def retry_failed():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    count = await asyncio.to_thread(manager.retry_failed_downloads)
    return {"message": f"Reset {count} failed downloads"}

@app.delete("/api/downloads/completed")
async def clear_completed():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    count = await asyncio.to_thread(manager.clear_completed_downloads)
    return {"message": f"Cleared {count} completed downloads"}

@app.delete("/api/downloads/failed")
async def clear_failed():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    count = await asyncio.to_thread(manager.clear_failed_downloads)
    return {"message": f"Cleared {count} failed downloads"}

@app.delete("/api/downloads/{item_id}")
async def remove_download(item_id: int):
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    count = await asyncio.to_thread(manager.remove_downloads, [item_id])
    if count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Download removed"}

@app.get("/api/stats")
async def get_stats():
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    items = await asyncio.to_thread(manager.db.get_all_downloads)
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
        "is_paused": not manager.pause_event.is_set(),
    }

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            if manager:
                items = await asyncio.to_thread(manager.db.get_all_downloads)
                stats = await get_stats()
                data = [
                    {
                        "id": i.id,
                        "title": i.title,
                        "status": i.status,
                        "download_speed": i.download_speed,
                        "eta": i.eta,
                        "progress": i.progress,
                    }
                    for i in items
                ]
                await websocket.send_json({"downloads": data, "stats": stats})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port)
