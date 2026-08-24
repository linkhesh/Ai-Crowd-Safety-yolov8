<h1 align="center">
  🤖 AI-Based Crowd Safety & Management System
</h1>

<h3 align="center">
  Real-Time Overcrowding Detection using YOLOv8
</h3>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=20&duration=3000&pause=1000&center=true&vCenter=true&width=700&lines=AI-Powered+Crowd+Monitoring;Real-Time+Person+Detection;Crowd+Density+Estimation;Overcrowding+Detection+%26+Alerts" alt="Typing SVG" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/YOLOv8-Computer%20Vision-111111?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white"/>
  <img src="https://img.shields.io/badge/Flask-Web%20Dashboard-000000?style=for-the-badge&logo=flask&logoColor=white"/>
</p>

---

## 🎯 Project Overview

An AI-powered crowd monitoring system designed to analyze CCTV video streams, estimate crowd density, detect overcrowding, and generate real-time alerts for proactive crowd safety management.

The system uses **YOLOv8-based object detection** to identify people in video streams and provides a web-based interface for monitoring crowd conditions.

---

## ✨ Key Features

- 👤 Real-time person detection
- 📊 Crowd density estimation
- 🚨 Overcrowding detection
- 🔔 Real-time alert generation
- 📹 CCTV/video stream analysis
- 🌐 Web-based monitoring dashboard
- ⚡ AI-powered computer vision processing

## 🔄 System Workflow

```text
📹 CCTV / Video Stream
          ↓
    🧠 YOLOv8 Model
          ↓
   👤 Person Detection
          ↓
   📊 Crowd Estimation
          ↓
  🚨 Overcrowding Check
          ↓
 🔔 Alert Generation
          ↓
🌐 Flask Web Dashboard
```
---

---

## 📸 Project Demo

### 👤 Real-Time Crowd Detection

![Real-Time Crowd Detection](dashboard.png)

### 🌐 Web Dashboard

![Web Dashboard](dashboard2.png)

### 🚨 Overcrowding Detection

![Overcrowding Detection](overcrowding-alert.png)

---

## 💻 Main Implementation

The core application is implemented in:

📄 **`dashbrdfn.py`**

The script handles the main crowd monitoring workflow, including video processing, YOLOv8-based detection, crowd analysis, and dashboard functionality.

👉 [View the main source code](./dashbrdfn.py)


---

## ▶️ How to Run

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/linkhesh/Ai-Crowd-Safety-yolov8.git
cd Ai-Crowd-Safety-yolov8
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Run the Application

```bash
python dashbrdfn.py
```

### 4️⃣ Open the Dashboard

After starting the application, open the local Flask address shown in the terminal.

---

## 📁 Project Structure

```text
Ai-Crowd-Safety-yolov8/
│
├── dashbrdfn.py
├── requirements.txt
├── dashboard.png
├── dashboard2.png
├── overcrowding-alert.png
└── README.md
```
