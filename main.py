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
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class DownloadRequest(BaseModel):
    url: str
    format: str = "mp3"


def download_task(url: str, fmt: str, job_id: str):
    outtmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}.%(ext)s")

    if fmt == "mp3":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "quiet": True,
        }
    else:
        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception as e:
        print(f"Download failed: {e}")


@app.get("/")
def root():
    return {"status": "ok", "service": "YT Downloader"}


@app.get("/info")
async def info(url: str):
    try:
        opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
            return {
                "title": data.get("title"),
                "duration": data.get("duration"),
                "uploader": data.get("uploader"),
                "thumbnail": data.get("thumbnail"),
                "view_count": data.get("view_count"),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download")
async def download(req: DownloadRequest, background_tasks: BackgroundTasks):
    if "youtube.com" not in req.url and "youtu.be" not in req.url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(download_task, req.url, req.format, job_id)

    return {
        "job_id": job_id,
        "status": "started",
        "file_url": f"/file/{job_id}",
    }


@app.get("/file/{job_id}")
async def get_file(job_id: str):
    matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}.*"))
    if not matches:
        raise HTTPException(
            status_code=404,
            detail="Not ready yet. Wait 20-60 seconds and retry.",
        )
    path = matches[0]
    return FileResponse(path, filename=os.path.basename(path))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
