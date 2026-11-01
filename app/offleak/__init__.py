"""Offleak: local privacy redaction for live video (faces, QR codes, phone numbers).

Layers, from the inside out:
  geometry / apple      - pure box maths and the Apple Vision adapter
  detection             - detector strategies (faces/heads, QR, phone text) and their decorators
  redaction             - the delay-buffered Redactor: optical flow, identity exemption, masks, blur strategy
  pipeline              - frame sources and the live / offline drivers
  obs, dock, twitch, ui - integrations (OBS workers, setup dock, Twitch alerts, debug UI)
  cli, launcher         - command-line and macOS entry points
"""
