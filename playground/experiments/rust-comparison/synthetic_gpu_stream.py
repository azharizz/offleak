#!/usr/bin/env python3
"""Provide synthetic stripes and a paired half-frame mask to the GPU source test."""
import threading
import time

import numpy as np
import gpu_worker as worker

thread = threading.Thread(target=worker.server)
thread.start()
image = np.zeros((720, 1280, 3), np.uint8)
image[:] = (((np.arange(1280) // 2) % 2) * 255).astype(np.uint8)[None, :, None]
mask = np.zeros((720, 1280), np.uint8)
mask[:, 640:] = 255
try:
    for _ in range(300):
        worker.publish(None, image, mask, None)
        time.sleep(.05)
finally:
    worker.running = False
    with worker.condition:
        worker.condition.notify_all()
    thread.join()
