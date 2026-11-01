"""Streamer exemption from face votes."""


def exempt(events, tid, frame, vote, keep):
    """Is this head the streamer? A tracked head follows its nearest vote within `keep` frames (ties reject:
    fail closed); an untracked head only has its own vote."""
    if tid < 0:
        return vote == 1
    near = [(abs(frame - f), s) for f, s in events.get(tid, ()) if abs(frame - f) <= keep]
    return bool(near) and min(near)[1] == 1
