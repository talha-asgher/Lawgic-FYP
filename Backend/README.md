# Lawgic Backend (FastAPI)

## Setup

### 1. Create and activate a virtual environment
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Create a `.env` file in this directory with your database connection and secret key:
```
DATABASE_URL=postgresql://user:password@localhost:5432/lawgic
SECRET_KEY=your_secret_key
```

### 4. Run the server
```bash
python -m uvicorn app.main:app --reload
```

The API will be available at: http://127.0.0.1:8000

Swagger docs: http://127.0.0.1:8000/docs
