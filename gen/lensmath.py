"""Field-of-view math shared by every generated page.

Mirrors the app: a body is a crop factor, and a lens on it frames like
focal length x crop factor on full frame. assets/lens-compare.js holds the
same formulas for the interactive tool; gen/tests/test_js_parity.py keeps
them in step.
"""

import math

FULL_FRAME_DIAGONAL = math.hypot(36.0, 24.0)

TABLE_FOCAL_LENGTHS = [14, 16, 18, 20, 24, 28, 35, 40, 50, 70, 85, 100, 135, 200, 300]
FRAME_FOCAL_LENGTHS = [24, 35, 50, 85, 135]
CLASSIC_EQUIVALENTS = [24, 35, 50, 85, 135]


def sensor_aspect(crop):
    """Micro Four Thirds and 44x33 medium format are 4:3; the rest are 3:2."""
    if math.isclose(crop, 2.0) or math.isclose(crop, 0.79):
        return (4, 3)
    return (3, 2)


def sensor_size(crop):
    """Width and height in mm, from the crop factor and the aspect ratio."""
    aw, ah = sensor_aspect(crop)
    diagonal = FULL_FRAME_DIAGONAL / crop
    unit = diagonal / math.hypot(aw, ah)
    return (aw * unit, ah * unit)


def equivalent(focal, crop):
    return focal * crop


def angle_of_view(dimension_mm, focal):
    return math.degrees(2 * math.atan(dimension_mm / (2 * focal)))


def angles(focal, crop):
    """Horizontal, vertical and diagonal angle of view in degrees."""
    w, h = sensor_size(crop)
    return (
        angle_of_view(w, focal),
        angle_of_view(h, focal),
        angle_of_view(math.hypot(w, h), focal),
    )


def focal_for_equivalent(equivalent_focal, crop):
    """The focal length that frames like equivalent_focal on full frame."""
    return equivalent_focal / crop


def frame_in_photo(focal, crop, photo_equivalent, photo_aspect, vertical=False):
    """Width and height of a lens's frame as fractions of a photo.

    The photo was taken at photo_equivalent (35 mm equivalent, diagonal) with
    photo_aspect = width / height. Both images are treated as rectilinear
    projections, so sizes compare in tangent-plane units (size / focal).
    A vertical frame puts the sensor's long side upright.
    """
    fw, fh = sensor_size(crop)
    if vertical:
        fw, fh = fh, fw
    frame_half_w = fw / 2 / focal
    frame_half_h = fh / 2 / focal
    unit = FULL_FRAME_DIAGONAL / math.hypot(photo_aspect, 1)
    photo_half_w = photo_aspect * unit / 2 / photo_equivalent
    photo_half_h = unit / 2 / photo_equivalent
    return (frame_half_w / photo_half_w, frame_half_h / photo_half_h)


# Distance tables on the camera pages and the tool page.
COVERAGE_FOCAL_LENGTHS = [24, 35, 50, 85, 135]
COVERAGE_DISTANCES = [1, 2, 3, 5, 10]
PORTRAIT_FOCAL_LENGTHS = [35, 50, 85, 135]
# Zoom ranges common for each sensor size, as (wide, long) focal lengths.
COMMON_ZOOMS = {
    "full_frame": [(16, 35), (24, 70), (24, 105), (70, 200)],
    "aps_c": [(10, 18), (18, 55), (18, 135), (55, 210)],
    "mft": [(12, 40), (12, 60), (14, 42), (40, 150)],
    "medium": [(32, 64), (45, 100), (100, 200)],
}
# A full-body portrait fits a 1.8 m person, head and shoulders about 0.5 m,
# both with the camera held vertically and the subject filling 90% of the
# frame height.
FULL_BODY_M = 1.8
HEAD_SHOULDERS_M = 0.5
PORTRAIT_FILL = 0.9
FOOT_M = 0.3048
# The person scene in the tool: the camera at eye level.
EYE_LEVEL_M = 1.5


def coverage(focal, crop, distance):
    """Width and height of the scene a lens captures at a distance.

    Camera held horizontally; the result is in the unit of distance. A
    rectilinear lens focused far away: size = distance x sensor size / focal.
    Close up, real lenses frame a little tighter than this.
    """
    w, h = sensor_size(crop)
    return (distance * w / focal, distance * h / focal)


def distance_to_fit(subject, focal, crop, vertical=True, fill=PORTRAIT_FILL):
    """How far to stand so a subject of this height fills `fill` of the frame.

    Vertical framing puts the sensor's long side upright. The result is in
    the unit of subject.
    """
    w, h = sensor_size(crop)
    upright = w if vertical else h
    return subject / fill * focal / upright


def format_key(crop):
    """COMMON_ZOOMS key for a crop factor; Canon's 1.6x shares the APS-C zooms."""
    if math.isclose(crop, 1.0):
        return "full_frame"
    if math.isclose(crop, 1.5) or math.isclose(crop, 1.6):
        return "aps_c"
    if math.isclose(crop, 2.0):
        return "mft"
    if math.isclose(crop, 0.79):
        return "medium"
    raise ValueError("unknown crop factor %s" % crop)
def focal_to_fit(subject, distance, crop, vertical=True, fill=PORTRAIT_FILL):
    """The focal length that fits a subject of this height at a distance.

    distance_to_fit solved for the focal length; subject and distance in the
    same unit.
    """
    w, h = sensor_size(crop)
    upright = w if vertical else h
    return distance * fill * upright / subject


def format_name(crop):
    if math.isclose(crop, 1.0):
        return "full frame"
    if math.isclose(crop, 1.5):
        return "APS-C"
    if math.isclose(crop, 1.6):
        return "Canon APS-C"
    if math.isclose(crop, 2.0):
        return "Micro Four Thirds"
    if math.isclose(crop, 0.79):
        return "44 x 33 medium format"
    raise ValueError("unknown crop factor %s" % crop)


def crop_label(crop):
    return ("%.2f" % crop).rstrip("0").rstrip(".") + "x"


def mm(value):
    """A focal length for prose: whole millimetres."""
    return "%d mm" % round(value)


def deg(value):
    return "%.1f°" % value
