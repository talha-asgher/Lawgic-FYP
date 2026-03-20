# 1. Create and activate virtualenv
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependancies
pip install fastapi uvicorn sqlalchemy psycopg2-binary python-dotenv passlib[bcrypt] python-jose pydantic email-validator python-multipart
pip install reportlab

# 3. Run the app
uvicorn main:app --reload
# hassan pcs
python -m uvicorn app.main:app --reload 
# 4. Swagger API
Open http://127.0.0.1:8000/docs
