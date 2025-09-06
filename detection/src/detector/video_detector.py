import cv2
import json
import os
import numpy as np
from pymongo import MongoClient
from ultralytics import YOLO
from confluent_kafka import Producer, Consumer

from .utils import (
    bbox_center,
    bbox_intersect,
    point_in_poly,
    write_on_image,
    get_polygon,
    to_builtin,
)
from .hand_fsm import GlobalFSM, Place, State


class VideoDetector:
    def __init__(self, cfg):
        self.cfg = cfg
        self.model = YOLO(cfg["MODEL_PATH"])

        # Mongodb config
        uri = f"mongodb+srv://{cfg['MONGO_USER']}:{cfg['MONGO_PASS']}@cluster0.ifbypwd.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        client = MongoClient(uri)
        database = client.get_database("pizza_project")
        self.violations = database.get_collection("violations")

        # Kafka config
        producer_conf = {"bootstrap.servers": cfg["KAFKA_BROKER"]}
        self.producer = Producer(producer_conf)

        consumer_conf = {
            "bootstrap.servers": cfg["KAFKA_BROKER"],
            "group.id": "pizza-vision-group",
            "auto.offset.reset": "earliest",
        }
        self.consumer = Consumer(consumer_conf)
        self.consumer.subscribe([cfg["CONSUMER_TOPIC"]])

        # classes
        classes = cfg["classes"]
        self.HAND = classes["HAND"]
        self.PERSON = classes["PERSON"]
        self.PIZZA = classes["PIZZA"]
        self.SCOOPER = classes["SCOOPER"]

        # thresholds
        thresholds = cfg["thresholds"]
        self.CONF = float(thresholds["conf"])
        self.colors = {i: tuple(c) for i, c in enumerate(cfg["palette"])}

        # ROIs and FSM
        self.rois = [
            [(519, 276), (649, 285), (613, 722), (441, 705)],
            [(476, 265), (530, 271), (486, 438), (435, 431)],
        ]  # [table, toppings]

        self.fsm = GlobalFSM(cfg)
        self.violation_count = 0
        self.violation_frames = 0
        self.read_before = False

    def get_rois(self, n=2):
        ret, frame = self.cap.read()
        if not ret:
            raise RuntimeError("Error: Couldn't read first frame.")
        for i in range(n):
            roi = get_polygon(frame)
            self.rois.append(roi)
        # reset to start
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def _draw_rois(self, frame):
        if len(self.rois) > 0 and self.rois[0]:
            cv2.polylines(frame, [np.array(self.rois[0])], True, (0, 255, 255), 2)
        if len(self.rois) > 1 and self.rois[1]:
            cv2.polylines(frame, [np.array(self.rois[1])], True, (255, 0, 255), 2)

    def _detections_by_class(self, results):
        dets = {self.HAND: [], self.PIZZA: [], self.SCOOPER: []}
        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return dets

        xyxy = boxes.xyxy.cpu().numpy()
        cls = boxes.cls.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy()

        for b, c, cf in zip(xyxy, cls, confs):
            if cf < self.CONF:
                continue
            if c in dets and self._should_draw(bbox_center(b)):
                dets[c].append({"bbox": b, "center": bbox_center(b)})
        return dets

    def _should_draw(self, center):
        if not self.rois or len(self.rois) < 2:
            return False
        in_table = point_in_poly(center, self.rois[0])
        in_toppings = point_in_poly(center, self.rois[1])
        return in_table or in_toppings

    def _draw_detections(self, frame, results):
        for box in results[0].boxes:
            conf = float(box.conf)
            cls = int(box.cls)
            if conf < self.CONF or cls == self.PERSON:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            center = bbox_center((x1, y1, x2, y2))
            if not self._should_draw(center):
                continue

            color = self.colors.get(cls, (0, 255, 0))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    def run(self):
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                continue

            frame_msg = json.loads(msg.value())
            frame_path = frame_msg["frame_path"]

            if frame_msg["frame_id"] == 1:
                if self.read_before:
                    break
                self.read_before = True

            # Read the frame
            frame = cv2.imread(frame_path)
            if frame is None:
                print(f"Failed to read {frame_path}")
                continue

            results = self.model(frame, conf=self.CONF)
            dets = self._detections_by_class(results)

            hands = dets[self.HAND]
            pizzas = dets[self.PIZZA]
            scoopers = dets[self.SCOOPER]

            # Default
            place = Place.IDLE
            touched_pizzas = []
            any_in_toppings = False
            any_in_table = False

            # Check all hands
            for hand in hands:
                center = hand["center"]
                in_toppings = point_in_poly(center, self.rois[1])
                in_table = point_in_poly(center, self.rois[0])

                if in_toppings:
                    any_in_toppings = True
                if in_table:
                    any_in_table = True
                    # check pizza touch
                    for pizza in pizzas:
                        if bbox_intersect(hand["bbox"], pizza["bbox"]):
                            touched_pizzas.append(pizza)

            # Resolve place
            if any_in_toppings:
                place = Place.IN_TOPPINGS
            elif any_in_table:
                place = Place.IN_TABLE

            violation_seen, state, toppings_timer, move_timer, scooper_timer = (
                self.fsm.update(place, touched_pizzas, scoopers)
            )
            if violation_seen:
                self.violation_count += 1
                self.violation_frames = 15

                # Collect bounding boxes + labels
                bbox_docs = []
                for cls_id, det_list in dets.items():
                    for det in det_list:
                        bbox_docs.append(
                            {
                                "label": self.cfg["classes"].get(cls_id, str(cls_id)),
                                "bbox": det["bbox"].tolist()
                                if hasattr(det["bbox"], "tolist")
                                else det["bbox"],
                            }
                        )

                frame_name = f"frame_{frame_msg['frame_id']:05d}.jpg"
                violation_frame_path = os.path.join(self.cfg["SERVER_DIR"], frame_name)
                cv2.imwrite(violation_frame_path, frame)

                # Create violation document
                violation_doc = {
                    "frame_id": frame_msg["frame_id"],
                    "frame_name": frame_name,
                    "timestamp": frame_msg["timestamp"],
                    "bounding_boxes": bbox_docs,
                    "violation_count": self.violation_count,
                    "rois": [list(map(list, roi)) for roi in self.rois],
                }

                # Insert into MongoDB
                violation_doc = to_builtin(violation_doc)
                self.violations.insert_one(violation_doc)
                print(f"[DB] Violation saved for {violation_frame_path}")

            # First line: state, place, violation count
            color = (0, 255, 0)  # green by default
            if state == State.IN_TOPPINGS:
                color = (0, 255, 0)  # green
            elif state == State.MOVING_TO_TABLE:
                color = (0, 255, 255)  # yellow
            elif state == State.TOUCHING_PIZZA:
                color = (0, 0, 255)  # red

            text1 = f"State: {state.value}, Place: {place.value}, Violation count: {self.violation_count}"
            write_on_image(
                frame,
                text1,
                org=(50, 50),
                font=cv2.FONT_HERSHEY_SIMPLEX,
                scale=1,
                thickness=2,
                color=color,
            )

            # Second line: timer/explanation
            if state == State.IDLE:
                text2 = ""
            elif state == State.IN_TOPPINGS:
                text2 = f"[{state.value}] Time in Toppings: {toppings_timer}"
            elif state == State.MOVING_TO_TABLE:
                text2 = f"[{state.value}] Checking touching pizza: {move_timer}"
            elif state == State.TOUCHING_PIZZA:
                text2 = f"[{state.value}] Checking using scooper: {scooper_timer}"

            write_on_image(
                frame,
                text2,
                org=(50, 100),
                font=cv2.FONT_HERSHEY_SIMPLEX,
                scale=1,
                thickness=2,
                color=color,
            )

            # Show VIOLATION for a few frames
            if self.violation_frames > 0:
                violation_text = "VIOLATION!"
                write_on_image(
                    frame,
                    violation_text,
                    org=(frame.shape[1] // 2 + 20, 50),
                    font=cv2.FONT_HERSHEY_SIMPLEX,
                    scale=1,
                    thickness=2,
                    color=(0, 0, 255),
                )
                self.violation_frames -= 1

            self._draw_detections(frame, results)
            self._draw_rois(frame)

            # replace frame with annotated one
            cv2.imwrite(frame_path, frame)

            # Publish annotated frame metadata
            annotated_msg = {
                "frame_id": frame_msg["frame_id"],
                "annotated_path": frame_path,
                "violation_count": self.violation_count,
                "place": place.name,
                "state": state.name,
                "timestamp": frame_msg["timestamp"],
            }
            self.producer.produce(
                self.cfg["PRODUCER_TOPIC"], value=json.dumps(annotated_msg)
            )
            self.producer.poll(0)
