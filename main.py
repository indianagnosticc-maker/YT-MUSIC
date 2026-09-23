import os
import uuid
import glob
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI(title="YT Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class DownloadRequest(BaseModel):
    url: str
    format: str = "mp3"

def download_task(url: str, job_id: str):
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        # YouTube datacenter IP block bypass
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios"]
            }
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/19.29.37 (Linux; U; Android 11) gzip"
        },
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"Download failed for {job_id}: {e}")

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/download")
async def download(req: DownloadRequest, background_tasks: BackgroundTasks):
    clean_url = req.url.split("?si=")[0].split("&si=")[0]
    if "youtube.com" not in clean_url and "youtu.be" not in clean_url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(download_task, clean_url, job_id)

    return {
        "job_id": job_id,
        "status": "started",
        "file_url": f"/file/{job_id}",
    }

# GET aur HEAD dono allow kiye hain taaki 405 error na aaye
@app.api_route("/file/{job_id}", methods=["GET", "HEAD"])
async def get_file(job_id: str):
    matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Not ready yet")
    path = matches[0]
    return FileResponse(path, filename="audio.mp3", media_type="audio/mpeg")
