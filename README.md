# Pizza Store Scooper Violation Detection 

This system monitors hygiene protocol compliance in a pizza store. Specifically, it detects whether workers are **using a scooper when picking up certain ingredients** (like proteins) from designated areas (ROIs – Regions of Interest).

The architecture is **microservices-based** and built with **YOLOv12**, **Kafka**, **MongoDB Atlas**, **FastAPI**, and **WebSockets**. Violations are detected using a **finite state machine (FSM)** logic.

## Architecture
```
pizza-vision-microservices/
  ├── docker-compose.yml            
  ├── .env.example                  # Example environment file (MongoDB credentials required)
  ├── README.md
  ├── data/                         # Persistent storage
  │  ├── frames/                    # Input video frames + annotated frames
  │  ├── kafka/                     # Kafka storage
  │  ├── server/                    # Violation images served by FastAPI
  ├── frame-reader/
  │  ├── Dockerfile
  │  ├── requirements.txt
  │  ├── src/
  │  │   ├── frame_reader.py/
  ├── detection/
  │  ├── Dockerfile
  │  ├── requirements.txt
  │  ├── src/
  │  │   ├── config.yaml            # Detection settings as colors, threshold, etc
  │  │   ├── main.py
  │  │   ├── detector/
  │  │   │   ├── video_detector.py  # Main detection logic
  │  │   │   ├── hand_fsm.py        # FSM states and transitions   
  │  │   │   ├── utils.py
  ├── streamer/
  │  ├── Dockerfile
  │  ├── requirements.txt
  │  ├── src/
  │  │   ├── main.py
  │  │   ├── streamer.py
  │  │   ├── templates/             # For dashboard.html
  │  │   ├── static/                # For Js and CSS
```

## Microservices

* **frame-reader**

  * Base: `python:3.10-slim`
  * Reads frames from a video/stream, saves them in frames dir, and publishes metadata to Kafka topic **`frames`**.

* **detection**

  * Base: `ultralytics/ultralytics:8.3.191-cpu` (replace with GPU image if available).
  * Consumes frames from **`frames`**, runs YOLO + FSM logic, saves annotated frames, stores violations in MongoDB Atlas + violation images in local `server/` dir, and publishes annotated frames metadata to **`detections`**.

* **streamer**

  * Base: `python:3.10-slim`
  * Uses FastAPI to:

    * Serve dashboard via WebSockets.
    * Expose MongoDB violation records via REST APIs.
    * Serve static files and violation images.

## Getting Started

### Prerequisites
* Docker + Docker Compose

### Installation

1. Clone the repo:
2. Create the `data/` directory structure:

   ```bash
   mkdir -p data/{frames,kafka,server}
   ```

3. Place your input files:

   * Video: `data/frames/video.mp4`
   * YOLO model: `data/frames/model.pt`

4. Run the stack:

   ```bash
   docker compose up --build
   ```

5. Open the dashboard:

   ```
   http://localhost:8765/
   ```

## API Documentation

### Static Mounts

* **`/images/*`** → serves violation images (from `server/` dir).
* **`/static/*`** → serves JS/CSS files.

### Routes

#### **Dashboard**

`GET /`

* Returns the dashboard UI (`dashboard.html`).

#### **WebSocket Stream**

`WS /ws`

* Real-time violation updates.
* Used by dashboard for live display.

#### **Get Violations**

`GET /violations?limit=20`

* Returns the latest violations.

#### **Get Single Violation**

`GET /violations/{frame_id}`

* Returns details for a specific frame ID.

#### **Delete Violation by ID**

`DELETE /violations/{violation_id}`

* Removes a violation by MongoDB ID.

#### **Delete All Violations**

`DELETE /violations`

* Clears the violations collection.


