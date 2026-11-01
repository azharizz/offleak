<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/offleak-banner.png" alt="Offleak: Live on. Leak off. A real-time privacy filter for IRL streams" width="100%">
</p>

# Offleak

## Live on. Leak off.

**Offleak** is a real-time privacy filter for IRL streamers. It runs inside **OBS** on your own computer and blurs **strangers' faces, QR codes and phone numbers** before a single frame reaches your viewers, while **your crew stays visible**. It connects to your **Twitch** channel, knows when you go live, and lets your moderators raise a privacy alert from chat with `!privacy`.

<p align="center">
  <a href="https://github.com/azharizz/offleak"><img src="https://img.shields.io/badge/OPEN%20SOURCE-0A0E18?style=for-the-badge&logo=github&logoColor=white" alt="Source repository"></a>
  <a href="https://dwzbpgm35mwo5.cloudfront.net"><img src="https://img.shields.io/badge/DOWNLOAD-8CE6D1?style=for-the-badge&logoColor=0A0E18" alt="Download Offleak"></a>
  <img src="https://img.shields.io/badge/OBS%20FILTER%20%C2%B7%20TWITCH-9146FF?style=for-the-badge&logo=twitch&logoColor=white" alt="OBS filter and Twitch">
  <img src="https://img.shields.io/badge/BUILT%20WITH%20CODEX-A9C9FF?style=for-the-badge&logoColor=0A0E18" alt="Built with Codex">
</p>

## Inspiration

An IRL stream only needs **one frame** to leak something it can never take back.

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-hero.gif" alt="One frame of a live street stream freezes, a face, a phone number and a QR code are spotted, and the frame is clipped and shared thousands of times" width="100%">
</p>

It keeps happening on the biggest channels:

- IShowSpeed flashed KSI's phone number to a live audience ([Dexerto](https://www.dexerto.com/entertainment/ishowspeed-blatantly-leaks-ksis-phone-number-on-instagram-1861669/), [Sportskeeda](https://www.sportskeeda.com/esports/ishowspeed-leaks-ksi-s-number-mistake)), and Adin Ross later leaked Speed's ([Dexerto](https://www.dexerto.com/youtube/adin-ross-apologizes-to-ishowspeed-after-leaking-his-number-2611960/)).
- RaKai was banned again after leaking an NBA star's number ([EarlyGame](https://earlygame.com/news/influencers/rakai-banned-again-after-leaking-nba-stars-phone-number-faces-permaban-risk)); a 17-year-old showed an FC Bayern star's private number live ([Mein-MMO](https://mein-mmo.de/en/youtube-17-year-old-shows-live-the-private-number-of-football-star-from-fc-bayern-3-seconds-later-the-phone-goes-crazy,896485)).
- Fans swarmed Kai Cenat and IShowSpeed after an address leaked on stream ([Dexerto](https://www.dexerto.com/entertainment/fans-swarm-kai-cenat-ishowspeed-after-address-leaks-on-stream-2194832/)).
- Bystanders never agreed to be streamed ([Dexerto](https://www.dexerto.com/entertainment/man-threatens-to-break-irl-streamers-camera-for-filming-in-public-1344237/)), and a boarding pass or ticket QR is enough to take over a booking ([One Mile at a Time](https://onemileatatime.com/news/traveler-learns-hard-way-dont-share-airline-ticket-details-online)).

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-leaks.gif" alt="Real headlines about streamers leaking phone numbers and addresses fly in, each stamped LEAKED" width="80%">
</p>

Live, there's no undo. Streamers can't watch every screen, ticket and stranger that drifts into frame, so we built the tool we wished they had: one that checks every frame *before* it goes out.

## What it does

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-reveal.gif" alt="A red leak splat morphs into the Offleak logo; faces, QR codes and phone numbers are blurred in turn" width="100%">
</p>

| Offleak capability | What it does | Why it matters |
| --- | --- | --- |
| **1 · Blurs strangers' faces** | Detects every face in frame and pixelates anyone who isn't on your list. | Bystanders keep their privacy; you keep streaming. |
| **2 · Keeps your crew visible** | Add people with one click from your webcam or a photo; Offleak recognises them and leaves them clear. | It's a filter for strangers, not for your show. |
| **3 · Masks QR codes and phone numbers** | Reads screens, tickets and paper in frame and covers any QR code or phone number it finds. | The leaks that end careers are usually small text. |
| **4 · Checks before it streams** | A short lookahead buffer means each frame is checked before it leaves OBS; if Offleak is ever unsure, it blurs the whole frame. | It fails closed, not open. |
| **5 · Lives in OBS** | An OBS filter on your camera plus a dock panel for people, switches, fps and status. | No new streaming software to learn. |
| **6 · Talks to Twitch** | Shows when you go live, and turns a moderator's `!privacy` in chat into an alert in your dock. | Your mods become a second pair of eyes. |

## Product walkthrough

<table>
  <tr>
    <td width="50%"><img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-install.gif" alt="The website download button is clicked, the DMG opens, and macOS and Windows installers run side by side"><br><sub><strong>1 · Install.</strong> Download for macOS or Windows; the installer sets up Python, the models and the OBS filter for you.</sub></td>
    <td width="50%"><img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-camera.gif" alt="An OBS window: plus, Video Capture Device, OK"><br><sub><strong>2 · Add your camera.</strong> A normal OBS Video Capture Device, nothing special.</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-setup.gif" alt="Copy the dock link from the terminal, paste it into Custom Browser Docks, add the Offleak filter"><br><sub><strong>3 · Dock and filter.</strong> Start Offleak, copy its private dock link, paste it into a browser dock, then add the Offleak filter to the camera.</sub></td>
    <td width="50%"><img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/demo-add-people.gif" alt="The real dock: Add people from webcam is clicked and Capturing from webcam appears"><br><sub><strong>4 · Keep your people.</strong> Real recording: one click on <em>Add people from webcam</em>.</sub></td>
  </tr>
</table>

### Three tests from the real OBS recording

| Result 01 · Screens | Result 02 · Crowd | Result 03 · Known vs. stranger |
| --- | --- | --- |
| ![Phone numbers and QR codes on a screen held to the camera are masked](https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/demo-screen-masked.gif) | ![A crowd shown on a screen behind the streamer is blurred face by face](https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/demo-crowd-blurred.gif) | ![An added person stays visible while the stranger next to him is blurred](https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/demo-known-visible.gif) |
| Numbers and QR codes on a screen: **masked**. | Every face in the crowd: **blurred**. | Added person: **visible**. Stranger beside him: **blurred**. |

<sub>Crops of the real OBS preview output. The streamer appears in the full recording but is cropped out here.</sub>

| The website | Copy the dock link | Custom Browser Docks |
| --- | --- | --- |
| ![Offleak website hero: Live on. Leak off.](https://raw.githubusercontent.com/azharizz/offleak/main/submission/screenshots/website-hero.jpg) | ![Terminal printing the private dock URL](https://raw.githubusercontent.com/azharizz/offleak/main/submission/screenshots/terminal-dock-link.jpg) | ![OBS Custom Browser Docks with the Offleak People dock](https://raw.githubusercontent.com/azharizz/offleak/main/submission/screenshots/obs-custom-browser-dock.jpg) |

| Add the filter | Filter properties | The Offleak dock |
| --- | --- | --- |
| ![OBS filter list with the Offleak direct filter](https://raw.githubusercontent.com/azharizz/offleak/main/submission/screenshots/obs-add-filter.jpg) | ![Offleak filter properties: lookahead, fps, blur switches](https://raw.githubusercontent.com/azharizz/offleak/main/submission/screenshots/obs-filter-properties.jpg) | ![Offleak dock: people, blur detection, video processing](https://raw.githubusercontent.com/azharizz/offleak/main/submission/screenshots/offleak-dock.jpg) |

## On Twitch

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-twitch.gif" alt="Connect Twitch in the dock, the channel goes live, a moderator types !privacy and the alert flies into the dock" width="100%">
</p>

| Twitch event | What Offleak does |
| --- | --- |
| **Connect Twitch** | OAuth in the dock with only the `user:read:chat` scope. No client secret in the app; the token stays in memory. |
| **`stream.online` / `stream.offline`** (EventSub) | The dock flips to **Live on Twitch**, so you can see protection is on before the stream starts. |
| **`channel.chat.message`** (EventSub) | When the broadcaster or a moderator types exactly `!privacy`, a privacy flag lands in your dock. |
| **What Twitch never gets** | Camera frames and face references never leave your computer. |

## How it works

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/offleak-architecture.gif" alt="Animated architecture: OBS camera to the Offleak filter, the local worker with face, QR and phone lanes, the redactor, OBS output and Twitch; the dock and Twitch EventSub alerts" width="100%">
</p>

1. The **Offleak filter** (an OBS plugin written in C) hands each camera frame to a **local worker** over a Unix socket on macOS, or a token-checked loopback TCP connection on Windows.
2. Three detector lanes run in parallel on the newest frame: **faces** (pose + YuNet or Apple Vision, with SFace matching against your people), **QR codes** (a QR detector model plus Apple Vision or OpenCV) and **phone numbers** (Apple Vision OCR or RapidOCR, then phone-number rules).
3. The **redactor** holds a lookahead buffer, carries every blur box onto the frames in between with sparse optical flow, and keeps known people clear.
4. If a detector stalls or is unsure, the whole frame is blurred. The filter shows the redacted frame in OBS, so the stream and any recording only ever see protected video.

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-pipeline.gif" alt="Frames flow from the camera through Offleak, get checked, wait in the lookahead buffer and go to the stream; an unsure frame is blurred whole" width="90%">
</p>

| Offleak will | Offleak won't |
| --- | --- |
| Check every output frame, and blur the whole frame when a detector stalls or is unsure. | Send your video, your face references or your viewers' data anywhere. |
| Keep the people you added visible, even inside a group photo. | Unblur someone just because they look similar: matching needs a confident face match. |
| Run on Apple Silicon, NVIDIA CUDA, DirectML for text on AMD/Intel, or the CPU. | Delay or redact your audio; audio is left untouched. |

## How we built it, with Codex

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-codex.gif" alt="Codex hub with four agents feeding a loop of experiment, tune, optimize and evaluate; human review approves; then build and port to macOS and Windows" width="100%">
</p>

Every step ran through **Codex**, as a **multi-agent** process with **human review** at each gate:

- **Research agents** surveyed detectors, OBS integration paths and real leak cases.
- **Model experiments** compared YuNet, SFace, SCRFD, Apple Vision, YOLO pose and head models, RapidOCR, QR detectors and BoT-SORT/ByteTrack in a playground with a synthetic ground-truth benchmark.
- **Tune → optimize → evaluate, again and again:** detector rates, holds, rotation handling, parallel detector passes (heads ~100 → ~68 ms, objects ~170 → ~127 ms on an M1 Pro) and fail-closed rules.
- **Human review** approved each change against the benchmark and the live OBS test before it moved on.
- **Build and port:** the clean app (strategy + decorator detectors behind one facade), the C OBS filter, the dock, Twitch EventSub, then macOS and Windows installers and the website.

| Technology | Role in Offleak |
| --- | --- |
| **OBS Studio 33 · C (libobs)** | The Offleak direct filter on the camera source; the Virtual Camera source as a fallback. |
| **Python 3.11** | Local worker, detectors, redactor, dock and Twitch monitor. |
| **PyTorch · Ultralytics** | Pose-based head finding; GPU order is CUDA → Apple MPS → CPU. |
| **OpenCV** | YuNet faces, SFace identity, QR detection, sparse optical-flow tracking. |
| **Apple Vision (PyObjC)** | On-device OCR, barcodes and faces on macOS. |
| **RapidOCR · ONNX Runtime DirectML** | Text reading on Windows, on any GPU. |
| **QRDet · phonenumbers** | QR-specific detection and phone-number validation. |
| **Flask** | The token-protected OBS dock on `127.0.0.1:8767`. |
| **Twitch EventSub (WebSocket)** | `stream.online` and `!privacy` chat alerts. |
| **DMG + AppleScript · NSIS** | One-click installers for macOS and Windows. |
| **Amazon S3 · CloudFront** | The website and downloads. |
| **Codex** | Multi-agent research, experiments, tuning, building and porting, with human review. |

## Results

Benchmark: random 4-second clips with pasted QR codes and phone numbers at known positions, plus random mirroring, rotation, low resolution, motion blur, JPEG and brightness changes, scored on a set never used for tuning, at live detector rates.

<p align="center">
  <img src="https://img.shields.io/badge/QR%20codes%20masked-99.5%25-A9C9FF?style=for-the-badge" alt="QR codes masked 99.5%">
  <img src="https://img.shields.io/badge/phone%20numbers%20masked-99.7%25-B7A6FF?style=for-the-badge" alt="Phone numbers masked 99.7%">
  <img src="https://img.shields.io/badge/bystanders%20blurred-98.3%25-8CE6D1?style=for-the-badge" alt="Bystanders blurred 98.3%">
  <img src="https://img.shields.io/badge/output-up%20to%2060%20fps-FFD28A?style=for-the-badge" alt="Up to 60 fps">
</p>

| Set | QR | Phone | Streamer visible | Bystanders blurred | Longest leak QR / phone |
| --- | --- | --- | --- | --- | --- |
| Upright | **99.5%** | **99.7%** | 91.0% | **98.3%** | 133 ms / 100 ms |
| Handheld rotation | 95.6% | 78.5% | 88.9% | 93.9% | 1.3 s / 4.0 s |

With every detector on every frame (offline), QR and phone were both 100% with zero exposure gap. A live run of a 176-second clip on an M1 Pro produced all 5,285 frames at 29.98 fps with 0 dropped and a flat 1.51 s delay. In the direct OBS filter at a 60 fps target, the worker processed about 44–51 frames/s on an M1 Pro.

## Challenges we ran into

- **Fast enough, safe enough.** Detectors can't run on every 60 fps frame, so blur boxes ride on optical flow between detections, and a stalled detector blurs everything instead of letting frames through.
- **Your crew vs. strangers.** Identity has to be confident before anyone is unblurred; group photos are split into separate face cards you can remove one by one.
- **Small, rotated text.** Phone numbers on a tilted phone or a held-up screen needed rotation probes, mirror votes and zoomed re-reads of screen crops.
- **Inside OBS, on two platforms.** A native C filter, a local worker and a token-protected dock, packaged for Apple Silicon and for Windows with CUDA, DirectML or CPU.

## Accomplishments we're proud of

<p align="center">
  <img src="https://raw.githubusercontent.com/azharizz/offleak/main/submission/assets/film-finale.gif" alt="The street from the opening, now protected: a scan line pixelates every face, the number and the QR code; Your stream, your rules; the Offleak logo" width="90%">
</p>

- A privacy filter that runs **inside OBS, on the streamer's own machine**, and fails closed.
- **Your people stay visible**: one click from the webcam, even from group photos.
- 99.5% of QR codes, 99.7% of phone numbers and 98.3% of bystanders protected on an unseen benchmark set at live rates.
- One-click installers for **macOS and Windows**, a website, and Twitch live status with moderator `!privacy` alerts.

## What we learned

The hardest part of a privacy tool isn't detection, it's deciding what happens when detection isn't sure. Offleak's answer is to look ahead, carry every box, and blur the whole frame rather than guess. And streamers don't want another app: it has to live where they already work, in OBS, and get out of the way.

## What's next

- Automatic OBS dock setup, so no link needs to be copied.
- Tracking tuned for fast handheld turns, where phone-number recall is lowest today.
- More languages and number formats, plus license plates and addresses on signs.
- A Linux build, and testing with more IRL streamers and moderators.

## Honest limits

- **Not a guarantee.** Detection can miss a face, a QR code or a very small number; review the output before relying on it live.
- **Twitch** status and alerts are built on EventSub; Offleak's protection never depends on Twitch being connected. The Twitch page in the film is a mock-up of a live channel.
- **Model licences:** Ultralytics and QRDet weights are AGPL-3.0, and Offleak is released under AGPL-3.0 too.

## Try it

- **Download:** [dwzbpgm35mwo5.cloudfront.net](https://dwzbpgm35mwo5.cloudfront.net) · [macOS (.dmg)](https://dwzbpgm35mwo5.cloudfront.net/downloads/Offleak-0.1.0.dmg) · [Windows (.exe)](https://dwzbpgm35mwo5.cloudfront.net/downloads/Offleak-Setup-0.1.0.exe)
- **Source:** [github.com/azharizz/offleak](https://github.com/azharizz/offleak)
- **Run from source:** see the [README](https://github.com/azharizz/offleak#run-from-source)
