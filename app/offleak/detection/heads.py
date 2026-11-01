"""Head detection: pose-tracked heads, merged faces, and per-track streamer votes."""
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from ..config import MODELS
from ..geometry import area, clip, iou, frontal, rot90, unrot_box, xyxy
from .faces import FaceGallery, FaceIds, FaceSource, PlatformFaces
from .orientation import Orientation, UprightProbe


def head_box(kp, box):
    """Head square from pose keypoints (nose, eyes, ears); falls back to the top of the person box."""
    x1, y1, x2, y2 = box
    pts = kp[:5][kp[:5, 2] > .3]
    if len(pts) >= 2:
        cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
        sh = kp[5:7][kp[5:7, 2] > .3]
        # ear-to-ear ~ head width; shoulder span ~ 2.2x head width
        s = max(np.ptp(pts[:, 0]) * 1.6, np.ptp(pts[:, 1]) * 2.5, np.ptp(sh[:, 0]) * .45 if len(sh) == 2 else 0, 16)
        return [cx - s * .55, cy - s * .65, cx + s * .55, cy + s * .55]
    # back-facing or occluded people: the top of the person box (a head detector scored worse on the benchmark)
    s = max(16, min((x2 - x1) * .6, (y2 - y1) * .35))
    cx = (x1 + x2) / 2
    return [cx - s / 2, y1, cx + s / 2, y1 + s]


class HeadDetector:
    """detect(frame) -> [[track_id, x1, y1, x2, y2, vote]]; vote 1 = streamer, -1 = clear stranger, 0 = unknown."""

    RESCORE_AFTER = 3  # a track that voted within this many passes is not re-scored; its vote covers it via --keep

    def __init__(self, gallery: FaceGallery, orientation: Orientation, device, tracker='bytetrack.yaml',
                 extra_faces: tuple[FaceSource, ...] = (), upright_probe: UprightProbe | None = None):
        from ultralytics import YOLO
        self.gallery, self.orientation, self.device, self.tracker = gallery, orientation, device, tracker
        self.extra_faces = list(extra_faces)
        self.upright_probe = upright_probe  # only when the backend reports no face roll
        # extra face sources (YuNet on CPU) run while pose runs on the GPU; both only read the upright frame
        self.pool = ThreadPoolExecutor(max(1, len(self.extra_faces)), thread_name_prefix='offleak-faces')
        self.pose = YOLO(str(MODELS / 'yolo11n-pose.pt'))
        self.ids = FaceIds()
        self.passes = 0
        self.last_vote = {}  # track id -> pass of its last SFace score

    def _pose_heads(self, upright, k, w, h):
        r = self.pose.track(upright, persist=True, tracker=self.tracker, imgsz=960, conf=.2, verbose=False, device=self.device)[0]
        ids = r.boxes.id.int().cpu().numpy() if r.boxes.id is not None else [-1] * len(r.boxes)
        people = []
        for box, tid, kp in zip(r.boxes.xyxy.cpu().numpy(), ids, r.keypoints.data.cpu().numpy()):
            head = unrot_box(head_box(kp, box), k, w, h)
            if not any(iou(head, p[1]) > .5 for p in people):  # pose emits duplicate boxes for close-ups; keep the first
                people.append([int(tid), head, 0])
        return people

    def detect(self, frame):
        self.passes += 1
        h, w = frame.shape[:2]
        primary = PlatformFaces.find(frame)
        if primary is not None:
            self.orientation.observe_rolls(primary[:, 15])
        elif self.upright_probe:
            self.upright_probe.observe(frame, self.orientation)
        k = self.orientation.rot
        upright = rot90(frame, k)
        extra = [self.pool.submit(source.find, upright, k, w, h) for source in self.extra_faces]
        people = self._pose_heads(upright, k, w, h)
        faces = [] if primary is None else [f[:15] for f in primary]
        for job in extra:
            for f in job.result():
                if all(iou(xyxy(f), xyxy(v)) < .3 for v in faces):
                    faces.append(f)
        taken = set()
        for f in sorted(faces, key=lambda f: -f[2] * f[3]):
            x, y, fw, fh = map(float, f[:4])
            cx, cy = x + fw / 2, y + fh / 2
            # a head owns only its largest face, and only one filling >= 35% of it: a small face whose centre falls
            # inside a big close-up head box belongs to someone behind (it used to veto the streamer)
            owners = [p for p in people if id(p) not in taken and p[1][0] <= cx <= p[1][2] and p[1][1] <= cy <= p[1][3]
                      and min(fw, fh) >= .35 * min(p[1][2] - p[1][0], p[1][3] - p[1][1])]
            owner = min(owners, key=lambda p: area(p[1])) if owners else None
            tid = owner[0] if owner else -1
            vote = self._vote(frame, f, tid, min(fw, fh))
            if owner:
                taken.add(id(owner))
                owner[1] = [min(owner[1][0], x), min(owner[1][1], y), max(owner[1][2], x + fw), max(owner[1][3], y + fh)]
                owner[2] = vote
            else:
                people.append([-1, [x, y, x + fw, y + fh], vote])
        self.ids.assign(people)
        if len(self.last_vote) > 5000:
            self.last_vote.clear()
        return [[tid, *clip(b, w, h), vote] for tid, b, vote in people]

    def _vote(self, frame, face, tid, size):
        """Only frontal faces vote: a streamer's profile scores like a stranger."""
        fresh = tid >= 0 and self.passes - self.last_vote.get(tid, -99) < self.RESCORE_AFTER
        if size < 24 or fresh or not frontal(face):
            return 0
        if tid >= 0:
            self.last_vote[tid] = self.passes
        return FaceGallery.vote(self.gallery.score(frame, face), size)
