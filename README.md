# 👁️ Argus AI — Intelligent Video Surveillance & Behavioral Analysis

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000?style=for-the-badge&logo=flask)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-FF6F00?style=for-the-badge)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

**Argus AI** is a scalable, multi-tenant video surveillance platform that leverages advanced computer vision (**YOLOv8**) to transform standard camera feeds into active behavioral intelligence. Designed for enterprise security, it detects structural intrusions, behavioral anomalies, and safety compliance breaches in real-time.

---

## 🌟 Key Features

### 🧠 Real-Time AI Detection Engine
* **Threat & Object Detection**: Utilizes Ultralytics YOLOv8 to identify unauthorized personnel, weapons, vehicles in restricted zones, and fallen individuals.
* **Dynamic Bounding & Analytics**: Real-time video frame annotation with severity-based risk categorization (`CRITICAL`, `WARNING`, `INFO`).
* **Multi-Source Ingestion**: Processes RTSP IP camera streams, local hardware webcams, and pre-recorded MP4/AVI security footage flawlessly.

### 🛡️ Enterprise Multi-Tenant Architecture
* **Role-Based Access Control (RBAC)**: Strict cryptographic isolation between `Admin` supervisors and `Client` tenants.
* **Tenant Data Privacy**: Clients only have visibility into cameras, event logs, and analytics explicitly bound to their `owner_id`.
* **Centralized Governance**: Dedicated admin hub for system-wide analytics, user lifecycle management, and global audit trails.

### 📊 Behavioral Dashboard & Incident Response
* **Live Asynchronous Alerts**: In-app toast notification system powered by background event polling for instant threat awareness.
* **Evidence Management**: Filterable behavioral logs linked to timestamped snapshot captures and incident classifications.
* **Interactive Analytics**: Daily and weekly threat progression charts generated via complex MongoDB aggregation pipelines.

---

## 📸 System Previews

### 🧠 Real-Time YOLOv8 Anomaly Detection & Evidence Capture
<p align="center">
  <img src="C:\Users\darsh\OneDrive\Pictures\Screenshot 2026-11-09 190509.png" alt="Argus AI Real-Time Detection" width="100%"/>
</p>

---

### 📊 Client Behavior Dashboard & Multi-Camera Control
| Client Behavior Dashboard | Self-Service Camera Management |
|:---:|:---:|
| <img src="C:\Users\darsh\OneDrive\Pictures\Screenshot 2026-11-09 190542.png" width="100%"/> | <img src="C:\Users\darsh\OneDrive\Pictures\Screenshot 2026-11-09 190631.png width="100%"/> |

---

### 🛡️ Admin System Governance & Global Threat Analytics
<p align="center">
  <img src="C:\Users\darsh\OneDrive\Pictures\Screenshot 2026-11-09 190356.png" alt="Admin Analytics Hub" width="100%"/>
</p>

## 🏗️ System Architecture

```text
                                    ┌──────────────────────┐
                                    │   Web Browsers / UI  │
                                    └──────────┬───────────┘
                                               │ HTTP / WebSocket
┌──────────────────────────────────────────────▼──────────────────────────────────────────────┐
│                                       Flask Web Engine                                      │
│                                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐  │
│  │ Auth & RBAC     │    │ Camera Manager  │    │ Analytics Hub   │    │ Live Streamer    │  │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘    └────────┬─────────┘  │
└───────────┼──────────────────────┼──────────────────────┼──────────────────────┼────────────┘
            │                      │                      │                      │
            ▼                      ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Core Processing Engines                                     │
│     ┌───────────────────────────────────┐       ┌──────────────────────────────────────┐    │
│     │    YOLOv8 Anomaly Classifier      │       │      Detector Event Dispatcher       │    │
│     └─────────────────┬─────────────────┘       └──────────────────┬───────────────────┘    │
└───────────────────────┼────────────────────────────────────────────┼────────────────────────┘
                        │                                            │
           ┌────────────▼────────────┐                  ┌────────────▼────────────┐
           │  MongoDB Atlas Database │                  │   Local Storage System  │
           │  (Users, Cameras, Logs) │                  │ (Static Frames/Uploads) │
           └─────────────────────────┘                  └─────────────────────────┘
🛠️ Tech Stack
Backend: Python 3.10+, Flask, Waitress (WSGI)
Computer Vision: OpenCV (cv2), Ultralytics YOLOv8, PyTorch
Database: MongoDB Atlas / PyMongo
Security: Bcrypt password hashing, Flask-Session management
Frontend: HTML5, Bootstrap 5, FontAwesome 6, Vanilla JS

🚀 Quick Start & Installation
1. Prerequisites
Python 3.10 or higher
MongoDB Atlas connection string (or local MongoDB server)
Compatible webcam (optional, for the Live Testing Lab)
2. Clone the Repository

git clone https://github.com/YOUR_USERNAME/argus-ai.git
cd argus-ai

3. Initialize Virtual Environment
# Windows
python -m venv .venv
.venv\Scripts\activate

4. Install Dependencies
pip install -r requirements.txt

5. Environment Configuration
Create a .env file in the root directory. Never commit this file to version control.

6. Boot the System
python run.py
Navigate to http://127.0.0.1:5000 in your browser.

🔒 Security Architecture Highlights
Thread-Safe Camera Allocation: Hardware video sources are locked to the active user's session to prevent unauthorized feed hijacking across tenants.
Strict Route Authorization: Every API and rendering route enforces multi-layered RBAC checks to prevent vertical and horizontal privilege escalation.
Failsafe Account Protections: Root administrators are structurally prevented from inadvertently disabling their own system access.