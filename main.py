from fastapi import FastAPI
from dotenv import load_dotenv
from supabase import create_client, Client
import os

from src.core.books.router import router as books_router
from src.core.user_roles.router import router as user_router

load_dotenv()
app = FastAPI()

supabase: Client = create_client(
    os.getenv("SUPABASE_DB_URL"), os.getenv("SUPABASE_KEY")
)

app.include_router(books_router)
app.include_router(user_router)


@app.get("/")
def read_root():
    return {"Hello": "World"}
