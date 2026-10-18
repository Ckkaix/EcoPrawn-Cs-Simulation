# EcoPrawn API

Standalone FastAPI backend for the EcoPrawn simulation dashboard.

## Run locally

From this directory:

```bash
python -m venv .venv
```

Activate the virtual environment, then install the dependencies:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn main:app --reload --port 8000
```

The health endpoint is available at `http://localhost:8000/api/health`.
Interactive API documentation is available at `http://localhost:8000/docs`.

## Creating a GitHub repository

Use the contents of this `backend` directory as the root of the new repository.
The `ingestion`, `models`, `reporting`, and `visualization` directories are
included because the API imports them at runtime.

Example:

```bash
git init
git add .
git commit -m "Create EcoPrawn API"
git branch -M main
git remote add origin <your-new-repository-url>
git push -u origin main
```
