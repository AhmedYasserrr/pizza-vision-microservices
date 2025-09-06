from aiokafka import AIOKafkaConsumer
import json
import cv2
import asyncio
from fastapi import WebSocket


class FrameStreamer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.consumer = None
        self.websocket_clients: set[WebSocket] = set()

    async def start_consumer(self):
        self.consumer = AIOKafkaConsumer(
            self.cfg["CONSUMER_TOPIC"],
            bootstrap_servers=self.cfg["KAFKA_BROKER"],
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        while True:
            try:
                await self.consumer.start()
                break
            except Exception as e:
                print(f"Kafka not ready yet: {e}")
                await asyncio.sleep(5)

        try:
            async for msg in self.consumer:
                frame_msg = msg.value
                frame_path = frame_msg.get("annotated_path")

                frame = cv2.imread(frame_path)
                if frame is None:
                    print(f"Failed to found frame {frame_path}")
                    continue

                success, jpg = cv2.imencode(".jpg", frame)
                if not success:
                    continue

                data = jpg.tobytes()
                await self.broadcast(data)

        except Exception as e:
            print(f"Kafka consumer failed: {e}")
        finally:
            await self.consumer.stop()

    async def broadcast(self, data: bytes):
        if not self.websocket_clients:
            return

        to_remove = set()
        for ws in self.websocket_clients:
            try:
                await ws.send_bytes(data)
            except Exception:
                to_remove.add(ws)

        self.websocket_clients -= to_remove
