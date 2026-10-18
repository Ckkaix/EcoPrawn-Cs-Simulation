# EcoPrawn CS Simulation

EcoPrawn is a React and FastAPI application for simulating pond water quality,
shrimp stocking, and production feasibility.

## Run locally

### 1. Start the FastAPI backend

Open PowerShell in the project folder:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

The backend API and interactive documentation are available at:

- http://localhost:8000/api/health
- http://localhost:8000/docs

Keep this terminal running.

### 2. Start the React frontend

Open a second PowerShell window in the project folder:

```powershell
cd frontend
npm install
npm run dev
```

Open the frontend at:

- http://localhost:5173

The frontend uses the Vite `/api` proxy to connect to the local backend.
