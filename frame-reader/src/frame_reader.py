import cv2
import os
import time
import json
from confluent_kafka import Producer

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "broker:29092")
TOPIC = os.getenv("KAFKA_TOPIC", "frames")
VIDEO_PATH = os.getenv("VIDEO_PATH", "0")
FRAME_DIR = os.getenv("FRAME_DIR", "/mnt/frames")

os.makedirs(FRAME_DIR, exist_ok=True)

# Kafka producer config
producer_conf = {"bootstrap.servers": KAFKA_BROKER}
producer = Producer(producer_conf)

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def send_with_retry(message, retries=5, delay=2):
    for attempt in range(1, retries + 1):
        try:
            producer.produce(
                TOPIC,
                value=json.dumps(message),
                callback=delivery_report
            )
            producer.poll(0)
            return True
        except BufferError as e:
            print(f"Local buffer full, waiting... {e}")
            time.sleep(delay)
        except Exception as e:
            print(f"Attempt {attempt}/{retries} failed: {e}")
            time.sleep(delay)
    return False

def main():
    cap = cv2.VideoCapture(0 if VIDEO_PATH == "0" else VIDEO_PATH)
    frame_id = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("End of video stream.")
            break
        # Save frame to shared volume
        frame_path = os.path.join(FRAME_DIR, f"frame_{frame_id:05d}.jpg")
        cv2.imwrite(frame_path, frame)

        # Publish metadata to Kafka
        message = {
            "frame_id": frame_id,
            "frame_path": frame_path,
            "timestamp": time.time()
        }
        success = send_with_retry(message)
        if not success:
            print(f"Dropped frame {frame_id} after retries")

        frame_id += 1
        time.sleep(1)

    producer.flush()
    cap.release()

if __name__ == "__main__":
    print("start")
    main()
