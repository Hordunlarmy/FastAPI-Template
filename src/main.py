import os
from contextlib import asynccontextmanager

import uvicorn
from decouple import config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src import database, logger, router

env = config("ENV", default="prod")
is_prod = env == "prod"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.initialize()
    logger.info(f"Application started for process {os.getpid()}")

    yield
    await database.close()
    logger.info(f"Application stopped for process {os.getpid()}")


app = FastAPI(
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_trailing_slash_middleware(request: Request, call_next):
    if request.url.path != "/" and not request.url.path.endswith("/"):
        request.scope["path"] = request.url.path + "/"
    response = await call_next(request)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=[config("ALLOWED_ORIGINS", default="*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=config("SECRET_KEY"))


app.include_router(router)


if __name__ == "__main__":
    logger.info("Starting the server")

    port = int(config("APP_PORT", default=8000)) if is_prod else 8002
    reload = False if is_prod else True
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload)
