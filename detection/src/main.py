import yaml
import os

from detector import VideoDetector

if __name__ == "__main__":
    with open("config.yaml", "r") as f:
        cfg = yaml.safe_load(f)

    cfg["KAFKA_BROKER"] = os.getenv("KAFKA_BROKER", "broker:29092")
    cfg["CONSUMER_TOPIC"] = os.getenv("CONSUMER_TOPIC", "frames")
    cfg["PRODUCER_TOPIC"] = os.getenv("PRODUCER_TOPIC", "detections")
    cfg["FRAME_DIR"] = os.getenv("FRAME_DIR", "/mnt/frames")
    cfg["MONGO_USER"] = os.getenv("MONGO_USER")
    cfg["MONGO_PASS"] = os.getenv("MONGO_PASS")

    os.makedirs(cfg["FRAME_DIR"], exist_ok=True)

    detector = VideoDetector(cfg)
    # detector.get_rois(n=2)
    detector.run()
