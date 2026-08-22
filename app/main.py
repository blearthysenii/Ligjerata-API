import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models
from app.database import Base, engine
from app.database_migrations import migrate_follows, migrate_lecture_media_columns, migrate_password_reset_codes, migrate_personalization_features, migrate_product_features, migrate_push_tokens, migrate_user_date_of_birth
from app.routers import admin, admin_content, auth, categories, content, lectures, me, personalization, speakers


app = FastAPI(
    title="Ligjerata API",
    version="1.0.0",
)


Base.metadata.create_all(bind=engine)
migrate_user_date_of_birth()
migrate_lecture_media_columns()
migrate_password_reset_codes()
migrate_push_tokens()
migrate_follows()
migrate_product_features()
migrate_personalization_features()

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8081,http://127.0.0.1:8081",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(personalization.router)
app.include_router(admin.router)
app.include_router(admin_content.router)
app.include_router(content.router)
app.include_router(speakers.router)
app.include_router(categories.router)
app.include_router(lectures.router)


@app.get("/")
def root():
    return {
        "message": "Ligjerata API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

@app.get("/db-test")
def db_test():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        return {
            "database": "connected",
            "result": result.scalar(),
        }
