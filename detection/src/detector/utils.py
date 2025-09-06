import cv2
import numpy as np


def bbox_center(b):
    x1, y1, x2, y2 = b
    return (0.5 * (x1 + x2), 0.5 * (y1 + y2))


def bbox_intersect(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    return (ix2 - ix1) > 0 and (iy2 - iy1) > 0


def point_in_poly(pt, poly):
    # pt=(x,y), poly=[(x,y), ...]
    return cv2.pointPolygonTest(np.array(poly, dtype=np.int32), pt, False) >= 0


# Global vars for polygon drawing
polygon_points = []
drawing_done = False


def draw_polygon(event, x, y, flags, param):
    global polygon_points, drawing_done

    if event == cv2.EVENT_LBUTTONDOWN and not drawing_done:
        polygon_points.append((x, y))

        # Stop after 4 points
        if len(polygon_points) == 4:
            drawing_done = True


def get_polygon(frame):
    """Pause on the frame until user clicks 4 points to form polygon."""
    global polygon_points, drawing_done
    polygon_points = []
    drawing_done = False

    clone = frame.copy()
    cv2.namedWindow("Draw Polygon", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Draw Polygon", 1200, 800)
    cv2.setMouseCallback("Draw Polygon", draw_polygon)

    while True:
        temp = clone.copy()
        # Draw lines for current polygon
        if len(polygon_points) > 1:
            cv2.polylines(temp, [np.array(polygon_points)], False, (0, 255, 255), 2)

        # If finished 4 points, draw closed polygon
        if drawing_done:
            cv2.polylines(temp, [np.array(polygon_points)], True, (0, 255, 0), 2)

        cv2.imshow("Draw Polygon", temp)

        key = cv2.waitKey(1) & 0xFF
        if drawing_done and key == ord("c"):  # press 'c' to confirm polygon
            break
        elif key == ord("r"):  # reset
            polygon_points = []
            drawing_done = False
        elif key == ord("q"):  # quit entirely
            exit()

    cv2.destroyWindow("Draw Polygon")
    return polygon_points


def write_on_image(frame, text, org, font, scale, thickness, color):
    cv2.putText(frame, text, org, font, scale, (0, 0, 0), thickness + 4, cv2.LINE_AA)
    cv2.putText(frame, text, org, font, scale, color, thickness, cv2.LINE_AA)


def to_builtin(obj):
    """Recursively convert numpy types and tuples to JSON-safe Python types."""
    if isinstance(obj, dict):
        return {k: to_builtin(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_builtin(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    else:
        return obj
