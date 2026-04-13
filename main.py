import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import database
import pipeline
from datetime import datetime

scheduler = AsyncIOScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    scheduler.add_job(
        run_pipeline,
        IntervalTrigger(hours=6),
        id="pipeline",
        replace_existing=True,
        next_run_time=datetime.now()  # run immediately on startup
    )
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="PrintScout", lifespan=lifespan)

async def run_pipeline():
    print(f"[{datetime.now().isoformat()}] Starting pipeline run...")
    database.set_status("running", "Scanning Reddit for trending products...")
    try:
        await pipeline.run()
        database.set_status("idle", f"Last run: {datetime.now().strftime('%b %d %H:%M')}")
        print("Pipeline complete.")
    except Exception as e:
        database.set_status("error", f"Error: {str(e)}")
        print(f"Pipeline error: {e}")

@app.get("/api/status")
def get_status():
    return database.get_status()

@app.get("/api/opportunities")
def get_opportunities(limit: int = 50):
    return database.get_opportunities(limit)

@app.get("/api/keyword/{keyword}")
def get_keyword(keyword: str):
    return database.get_keyword_detail(keyword)

@app.get("/api/history")
def get_history(keyword: str, days: int = 14):
    return database.get_keyword_history(keyword, days)

@app.post("/api/trigger")
async def trigger_pipeline(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_pipeline)
    return {"message": "Pipeline triggered"}

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return FileResponse("static/index.html")
