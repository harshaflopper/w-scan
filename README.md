# Mediscan: AI-Powered Clinical Wound Monitoring System 🩺✨

## Overview

- **Mediscan** is an advanced clinical-grade wound monitoring application designed to assist patients and healthcare professionals in tracking wound healing, analyzing tissue composition, and providing evidence-based care plans.
- It uses a multimodal approach, combining **Computer Vision (OpenCV)** for precise real-world scale calibration and **Google Gemini Vision AI** for deep clinical reasoning and trajectory forecasting.

## Architecture

The system is built with a modern tech stack, separating frontend, backend, and computer vision pipelines for maximum scalability, performance, and security.

![Mediscan AI Architecture](images/architecture.png)

### Tech Stack:

*   **Frontend:** React, Vite, React Router, Custom CSS (ChatGPT Dark Mode aesthetic), Three.js (Binary Singularities background), Lucide Icons.
*   **Backend:** FastAPI (Python).
*   **Database:** Supabase (PostgreSQL).
*   **AI/ML:**
    *   **Computer Vision Pipeline:** OpenCV for reference coin detection, bounding box extraction, and sub-millimeter auto-calibration.
    *   **Clinical Vision & Reasoning Agent:** Google Gemini Vision API (Multimodal reasoning).
*   **Authentication:** Clerk.

## How Our AI Excels 🧠

*   **Sub-Millimeter Precision (OpenCV):** Instead of relying on manual clinical estimates, our CV pipeline uses a standard reference coin to auto-calibrate image scale. It mathematically extracts the exact surface area ($cm^2$), perimeter, and circularity of the wound bed.
*   **Multimodal Gemini Vision:** We leverage the immense visual reasoning capabilities of **Google Gemini**. The model is prompted with structured, pre-processed visual data to identify Granulation, Slough, and Necrotic tissue percentages directly from the image.
*   **Evidence-Based Protocols:** Our AI agent doesn't hallucinate treatments. It computes standard medical indices like the **BWAT (Bates-Jensen Wound Assessment Tool)**, **NERDS** for localized infection screening, and the **Gilman parameter** for true healing velocity.
*   **Dual-Persona Outputs:** The LLM generates two distinct reports simultaneously: a terse, technical JSON payload for clinical handover and metric graphing, and an empathetic, jargon-free plain-English care plan for the patient.

## Features

*   **Auto-Calibrated Scanning:** Upload any wound photo with a reference coin. The system auto-detects boundaries and calculates true physical dimensions.
*   **8-Step Clinical Analysis:** Automated tissue segmentation and clinical index scoring.
*   **Infection Risk Screening:** AI flags low, moderate, high, or critical infection risks based on visible symptoms (erythema, exudate, maceration).
*   **Longitudinal Tracking Dashboard:** Compare historical sessions side-by-side, view healing velocity gauges, and track area reduction over time.
*   **Pharmacy Recommendations:** The AI suggests specific OTC dressing products (e.g., Alginate, Hydrocolloid) tailored to the wound's exudate and tissue profile, complete with links to purchase.
*   **Immersive Interface:** A hyper-modern, clinical dark mode UI backed by a stunning 3D Binary Singularities accretion disk simulation.

## Screenshots

Here are some glimpses of the Mediscan application:

*Wound Upload & Detection Interface.*
![Wound Upload](images/Screenshot%202026-05-16%20005329.png)

*Scale Calibration using Reference Coin.*
![Calibration](images/Screenshot%202026-05-16%20005423.png)

*Deep Clinical Analysis & Care Plan.*
![Results & Care Plan](images/Screenshot%202026-05-16%20011827.png)

*Longitudinal Tracking Dashboard.*
![Tracking Dashboard](images/Screenshot%202026-05-16%20012014.png)

## Getting Started

### Prerequisites

*   reactjs
*   python 3.10+
*   Google Cloud Project with Gemini API Key
*   Supabase Project (https://supabase.com/)
*   Clerk Account (https://clerk.dev/)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/harshaflopper/w-scan.git
    cd m-scan
    ```

### Frontend Setup (`frontend` directory)

1.  **Navigate to the frontend directory:**
    ```bash
    cd frontend
    ```
2.  **Install dependencies:**
    ```bash
    npm install
    ```
3.  **Set up environment variables:**
    Create a `.env.local` file in the `frontend` directory:
    ```env
    VITE_CLERK_PUBLISHABLE_KEY=<your_clerk_publishable_key>
    ```
4.  **Run the development server:**
    ```bash
    npm run dev
    ```
    The frontend will be available at `http://localhost:5173`.

### Backend Setup (`backend` directory)

1.  **Navigate to the backend directory (from the project root):**
    ```bash
    cd backend
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv .venv
    # On Windows
    .venv\Scripts\activate
    # On Mac/Linux
    source .venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Set up environment variables:**
    Create a `.env` file in the `backend` directory (or copy `.env.example`):
    ```env
    GEMINI_API_KEY=<your_gemini_api_key>
    SUPABASE_URL=<your_supabase_project_url>
    SUPABASE_KEY=<your_supabase_anon_key>
    ```
5.  **Run the server:**
    ```bash
    uvicorn main:app --reload --port 8000
    ```
    The API will be available at `http://localhost:8000`.
