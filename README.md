# Offleak

Offleak is an experimental privacy tool for IRL video streams. It aims to blur QR codes, phone numbers, and bystanders while keeping selected people visible. It is a research prototype: detection misses and identity errors can expose private information, and it is not a production privacy guarantee.

To try the OBS integration on an Apple Silicon Mac, double-click **Install Offleak.command**, then **Start Offleak.command**. It currently requires OBS Studio 33.0.1, Homebrew, and Apple's Command Line Tools; the installer can install Python and FFmpeg through Homebrew. Setup and the experiment reports are in [playground/README.md](playground/README.md). This repository does not include locally uploaded videos, generated outputs, or downloaded model weights.

The OBS worker targets 30 FPS with a 15-second buffer by default. See the [performance and privacy guide](playground/README.md#performance-and-privacy) for the 15 FPS option, status counters, experimental features, and known limitations.
