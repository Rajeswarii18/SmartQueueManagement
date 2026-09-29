# 🏥 SmartQueue Pro - Healthcare Queue & Dataset Management System

SmartQueue Pro is a modern, full-stack intelligent queue management application built for hospitals and healthcare facilities (The Nexus Medical Center). It streamlines patient intake, priority emergency triage, counter workstation dispatching, and historical queue dataset analytics.

---

## ✨ Key Features

- **🏥 Healthcare Intake Kiosk**: Patient self-service token printing with SMS/Email notifications and VIP / Senior Priority access.
- **📺 Big Screen TV Board**: Airport/hospital style digital calling display with Web Speech API Text-to-Speech (TTS) audio announcements (*"Ticket A-005, please proceed to Counter 1"*).
- **🎧 Counter Agent Workstations**: Live counter workstation panels to call next patient, handle visits, and log no-shows.
- **📈 Dataset & Analytics Hub**:
  - **Auto Dataset Seeder**: Generates 500+ realistic historical patient intake records across peak operating hours (08:00 - 18:00).
  - **4 Interactive Charts**: Hourly traffic distribution, service demand share, counter handle times & throughput, and customer CSAT satisfaction spread.
  - **Filterable Dataset Table**: Search & paginate through historical records by patient name, email, ticket, service, or status.
  - **CSV & JSON Export / Import**: Download or upload historical dataset logs.

---

## 🛠️ Tech Stack

- **Backend**: Python 3.x, Flask, SQLite3
- **Frontend**: HTML5, Vanilla CSS3 (Glassmorphic Dark Mode), Vanilla JavaScript
- **Data Visualization**: Chart.js
- **Audio Announcements**: Web Speech API

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/Rajeswarii18/SmartQueueManagement.git
cd SmartQueueManagement
```

### 2. Set up virtual environment & install dependencies
```bash
python -m venv venv

# On Windows:
.\venv\Scripts\activate

# On macOS / Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Run the server
```bash
python app.py
```

Access the application in your browser at: **`http://127.0.0.1:5000`**

---

## 📄 License
MIT License
