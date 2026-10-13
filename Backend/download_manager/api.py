import asyncio
import contextlib
from typing import List, Dict, Any, Optional

from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .manager import DownloadManager
from .models import DownloadItem
from .config import config
from .cookies import CookieManager

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

app = FastAPI(title="Sharky Download Engine API", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "Sharky", "version": "3.0.0"}


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

@app.get("/api/downloads/{item_id}/file")
async def download_file(item_id: int):
    if not manager:
        raise HTTPException(status_code=503, detail="Manager not initialized")
    item = await asyncio.to_thread(manager.db.get_download_by_id, item_id)
    if not item or not item.file_path:
        raise HTTPException(status_code=404, detail="File path not recorded for this item")

    file_path = Path(item.file_path)
    if not file_path.exists():
        # Fallback check inside configured subdirectories
        filename = file_path.name
        for sub in [config.VIDEODIR, config.AUDIODIR, config.FILESDIR, config.TORRENTSDIR]:
            candidate = sub / filename
            if candidate.exists():
                file_path = candidate
                break

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found on disk: {file_path.name}")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream"
    )

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
                        "url": i.url,
                        "title": i.title,
                        "status": i.status,
                        "download_type": i.download_type,
                        "download_speed": i.download_speed,
                        "eta": i.eta,
                        "progress": i.progress,
                        "file_size": i.file_size,
                        "downloaded_bytes": i.downloaded_bytes,
                        "error_message": i.error_message,
                        "file_path": i.file_path,
                    }
                    for i in items
                ]
                await websocket.send_json({"downloads": data, "stats": stats})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass

class SettingsModel(BaseModel):
    download_dir: Optional[str] = None
    concurrent_downloads: Optional[int] = None
    download_speed_limit: Optional[int] = None
    aria2c_rpc_port: Optional[int] = None
    aria2c_secret: Optional[str] = None
    qbittorrent_host: Optional[str] = None
    qbittorrent_username: Optional[str] = None
    qbittorrent_password: Optional[str] = None
    cookie_max_age: Optional[int] = None
    cookie_manual_path: Optional[str] = None
    cookie_browser_order: Optional[List[str]] = None

def get_settings_dict():
    return {
        "download_dir": str(config.BASEDIR),
        "concurrent_downloads": config.CONCURRENTDOWNLOADS,
        "download_speed_limit": config.DOWNLOAD_SPEED_LIMIT,
        "aria2c_rpc_port": config.ARIA2C_RPC_PORT,
        "aria2c_secret": config.ARIA2C_SECRET,
        "qbittorrent_host": config.QBITTORRENT_HOST,
        "qbittorrent_username": config.QBITTORRENT_USERNAME,
        "cookie_max_age": config.COOKIE_MAX_AGE,
        "cookie_manual_path": config.COOKIE_MANUAL_PATH,
        "cookie_browser_order": config.COOKIE_BROWSER_ORDER,
    }

@app.get("/api/settings")
async def get_settings():
    return get_settings_dict()

@app.put("/api/settings")
async def update_settings(req: SettingsModel):
    if req.download_dir is not None and req.download_dir.strip():
        success = config.set_download_directory(req.download_dir.strip())
        if not success:
            raise HTTPException(status_code=400, detail="Invalid download directory path")

    if req.concurrent_downloads is not None:
        if not (1 <= req.concurrent_downloads <= 64):
            raise HTTPException(status_code=400, detail="concurrent_downloads must be between 1 and 64")
        config.CONCURRENTDOWNLOADS = req.concurrent_downloads

    if req.download_speed_limit is not None:
        if req.download_speed_limit < 0:
            raise HTTPException(status_code=400, detail="download_speed_limit must be >= 0")
        config.DOWNLOAD_SPEED_LIMIT = req.download_speed_limit

    if req.aria2c_rpc_port is not None:
        if not (1024 <= req.aria2c_rpc_port <= 65535):
            raise HTTPException(status_code=400, detail="aria2c_rpc_port must be between 1024 and 65535")
        config.ARIA2C_RPC_PORT = req.aria2c_rpc_port

    if req.aria2c_secret is not None:
        config.ARIA2C_SECRET = req.aria2c_secret

    if req.qbittorrent_host is not None:
        config.QBITTORRENT_HOST = req.qbittorrent_host
    if req.qbittorrent_username is not None:
        config.QBITTORRENT_USERNAME = req.qbittorrent_username
    if req.qbittorrent_password is not None:
        config.QBITTORRENT_PASSWORD = req.qbittorrent_password

    if req.cookie_max_age is not None:
        if req.cookie_max_age <= 0:
            raise HTTPException(status_code=400, detail="cookie_max_age must be > 0")
        config.COOKIE_MAX_AGE = req.cookie_max_age

    if req.cookie_manual_path is not None:
        config.COOKIE_MANUAL_PATH = req.cookie_manual_path.strip() or None

    if req.cookie_browser_order is not None:
        config.COOKIE_BROWSER_ORDER = req.cookie_browser_order

    config.save_settings()
    return {"message": "Settings updated successfully", "settings": get_settings_dict()}

@app.get("/api/settings/cookies/status")
async def get_cookie_status():
    cm = CookieManager(config)
    return cm.get_cookie_status()

@app.post("/api/settings/cookies/clear")
async def clear_cached_cookies():
    cm = CookieManager(config)
    cm.clear_cached_cookies()
    return {"message": "Cached cookies cleared"}

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port)
