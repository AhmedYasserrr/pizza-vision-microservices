import asyncio
import os
import uvicorn
from pymongo import MongoClient
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from streamer import FrameStreamer
from bson import ObjectId

cfg = {
    "KAFKA_BROKER": os.getenv("KAFKA_BROKER", "broker:29092"),
    "CONSUMER_TOPIC": os.getenv("CONSUMER_TOPIC", "detections"),
    "FRAME_DIR": os.getenv("FRAME_DIR", "/mnt/frames"),
    "SERVER_DIR": os.getenv("SERVER_DIR", "/mnt/server"),
    "WEBSOCKET_HOST": os.getenv("WEBSOCKET_HOST", "0.0.0.0"),
    "WEBSOCKET_PORT": int(os.getenv("WEBSOCKET_PORT", "8765")),
    "MONGO_USER": os.getenv("MONGO_USER"),
    "MONGO_PASS": os.getenv("MONGO_PASS"),
}

# MongoDB setup
uri = f"mongodb+srv://{cfg['MONGO_USER']}:{cfg['MONGO_PASS']}@cluster0.ifbypwd.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(uri)
db = client.get_database("pizza_project")
violations_col = db.get_collection("violations")


streamer = FrameStreamer(cfg)
app = FastAPI()

# ------------------- Static mounting -------------------
app.mount("/images", StaticFiles(directory=cfg["SERVER_DIR"]), name="images")
app.mount("/static", StaticFiles(directory="static"), name="static")


# ------------------- Routes -------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    streamer.websocket_clients.add(ws)
    print("Client connected")
    try:
        while True:
            # We don’t expect messages from clients, but must await something
            await ws.receive_text()
    except WebSocketDisconnect:
        print("Client disconnected")
        streamer.websocket_clients.remove(ws)


# Startup event to run Kafka consumer
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(streamer.start_consumer())


# Violations REST APIs
@app.get("/violations")
def get_violations(limit: int = 20):
    """Return latest violations"""
    docs = list(violations_col.find().sort("timestamp", -1).limit(limit))
    for d in docs:
        d["_id"] = str(d["_id"])
        # Convert float timestamp -> human-readable
        if isinstance(d.get("timestamp"), (int, float)):
            d["timestamp"] = datetime.fromtimestamp(d["timestamp"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    return JSONResponse(docs)


@app.get("/violations/{frame_id}")
def get_violation(frame_id: str):
    doc = violations_col.find_one({"frame_id": int(frame_id)})
    if not doc:
        return JSONResponse({"error": "Not found"}, status_code=404)
    doc["_id"] = str(doc["_id"])
    if isinstance(doc.get("timestamp"), (int, float)):
        doc["timestamp"] = datetime.fromtimestamp(doc["timestamp"]).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    return JSONResponse(doc)


@app.delete("/violations/{violation_id}")
async def delete_violation(violation_id: str):
    try:
        oid = ObjectId(violation_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid violation id format")

    result = violations_col.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Violation not found")

    return {"status": "success", "deleted_id": violation_id}


@app.delete("/violations")
async def delete_all_violations():
    result = violations_col.delete_many({})
    return {"status": "success", "deleted_count": result.deleted_count}


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host=cfg["WEBSOCKET_HOST"], port=cfg["WEBSOCKET_PORT"], reload=True
    )
