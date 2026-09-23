import os
import uuid
import glob
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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

def download_stream(url: str, job_id: str):
    # Free converter engine call
    api_endpoint = f"https://api.vevioz.com/api/button/mp3/{url}"
    out_file = os.path.join(DOWNLOAD_DIR, f"{job_id}.mp3")
    
    # Fallback to direct download via cobalt/public service if needed
    try:
        payload = {"url": url, "downloadMode": "audio", "audioFormat": "mp3"}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        res = requests.post("https://api.cobalt.tools/api/json", json=payload, headers=headers, timeout=20)
        
        if res.status_code == 200 and "url" in res.json():
            stream_url = res.json()["url"]
            with requests.get(stream_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(out_file, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            return
    except Exception as e:
        print(f"Cobalt engine failed: {e}")

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/download")
async def download(req: DownloadRequest, background_tasks: BackgroundTasks):
    clean_url = req.url.split("?si=")[0].split("&si=")[0]
    if "youtube.com" not in clean_url and "youtu.be" not in clean_url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(download_stream, clean_url, job_id)

    return {
        "job_id": job_id,
        "status": "started",
        "file_url": f"/file/{job_id}",
    }

@app.api_route("/file/{job_id}", methods=["GET", "HEAD"])
async def get_file(job_id: str):
    matches = glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="Processing... wait 10-15 seconds.")
    path = matches[0]
    return FileResponse(path, filename="song.mp3", media_type="audio/mpeg")
