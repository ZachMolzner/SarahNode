# SarahNode — Local-First Personal AI Assistant

SarahNode is a **full-stack, real-time personal AI assistant platform** designed to run locally and serve multiple devices (desktop, tablet, and mobile) over a local network.

It combines **LLM interaction, text-to-speech (TTS), and an event-driven architecture** to create a responsive, extensible AI system focused on privacy, performance, and modular design.

---

## 🚀 Overview

SarahNode explores a **local-first approach to AI systems**, where the backend runs on your machine and the interface is accessible across devices on the same network.

Instead of relying entirely on cloud-based assistants, this project is designed to give developers:

* More control over AI workflows
* Real-time responsiveness
* A modular foundation for future AI integrations

---

## 🧠 Why SarahNode?

Most AI assistants today are:

* Fully cloud-dependent
* Closed ecosystems
* Limited in customization

SarahNode takes a different approach:

* 🏠 **Local-first architecture** → runs on your own machine
* ⚡ **Real-time communication** → powered by WebSockets
* 🧩 **Modular AI pipeline** → plug-and-play components
* 📱 **Multi-device support** → desktop, tablet, and phone
* 🔒 **Privacy-focused design** → your data stays local

---

## 🏗️ Architecture

### Frontend

* React + Vite + TypeScript
* Responsive dashboard UI
* Designed for cross-device usage

### Backend

* FastAPI (Python)
* Handles AI orchestration and event flow

### Communication Layer

* WebSocket event bus
* Enables real-time updates between backend and UI

### AI Pipeline

* LLM Adapter (OpenAI - currently mocked)
* TTS Adapter (ElevenLabs - currently mocked)
* Avatar/Event Bridge (placeholder for future integration)

### Data Flow

User Input
→ Moderation Layer
→ LLM Processing
→ TTS Generation
→ UI Update
→ Avatar/Event Output

---

## ✨ Key Features

* ⚡ Real-time AI responses via WebSockets
* 🧠 Modular AI adapter system (LLM, TTS, future integrations)
* 🏠 Local-first backend accessible across devices
* 📡 Event-driven architecture for scalability
* 📱 Responsive UI (desktop + mobile friendly)
* 🔌 Designed for future avatar / visual AI systems

---

## 📦 Project Structure

```
SarahNode/
├── backend/        # FastAPI backend (AI orchestration)
├── frontend/       # React + Vite frontend dashboard
├── docs/           # Architecture and planning docs
├── README.md
└── .gitignore
```

---

## ⚙️ Getting Started

### 1. Clone the repository

```
git clone https://github.com/ZachMolzner/SarahNode.git
cd SarahNode
```

---

### 2. Backend Setup (FastAPI)

```
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate (Windows)
pip install -r requirements.txt

uvicorn main:app --reload
```

Backend runs on:

```
http://localhost:8000
```

---

### 3. Frontend Setup (React + Vite)

```
cd frontend
npm install
npm run dev
```

Frontend runs on:

```
http://localhost:5173
```

---

### 4. Access Across Devices

To access from your phone/tablet:

* Find your local IP (e.g. `192.168.x.x`)
* Open:

```
http://<your-local-ip>:5173
```

---

## 🧪 Current Status

* ✅ Full-stack MVP architecture complete
* ✅ WebSocket event system implemented
* ✅ Mock AI pipeline connected end-to-end
* ⚠️ LLM + TTS currently mocked for development

---

## 🛣️ Roadmap

* [ ] Integrate real LLM provider (OpenAI / local models)
* [ ] Implement persistent memory system
* [ ] Add real TTS pipeline
* [ ] Build avatar / visual representation layer
* [ ] Optimize mobile experience
* [ ] Add authentication + user profiles
* [ ] Dockerize for easy deployment

---

## 🧩 Future Vision

SarahNode is designed as a **foundation for next-generation personal AI systems**, including:

* Voice-driven assistants
* AI companions / avatars
* Smart home integrations
* Developer-controlled AI workflows

---

## 👨‍💻 Author

**Zachery Molzner**

* Full-Stack Developer (MERN + Python)
* Educator transitioning into Software Engineering

GitHub: https://github.com/ZachMolzner

---

## 📄 License

This project is open-source and available under the MIT License.
