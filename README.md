# EcoPrawn React + FastAPI Application

This folder contains the new EcoPrawn application. It is separate from the
legacy Streamlit application in the repository root (`app.py`).

## Start the FastAPI backend

Open a terminal in `backend`:

```bash
python -m venv .venv
```

Activate the virtual environment, install the dependencies, and start the API:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Start the React frontend

Open a second terminal in `frontend`:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

The frontend uses the Vite `/api` proxy to connect to the local backend by
default. To use another API URL, set `VITE_API_URL` before starting Vite.

## Create a separate GitHub repository

Use the contents of this `new-app` directory as the root of the new repository.
It includes both the React frontend and the self-contained FastAPI backend.

```bash
git init
git add .
git commit -m "Create EcoPrawn React and FastAPI application"
git branch -M main
git remote add origin <your-new-repository-url>
git push -u origin main
```
