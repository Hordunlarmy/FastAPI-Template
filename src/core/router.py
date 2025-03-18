from fastapi import APIRouter

core = APIRouter()


@core.get("/")
async def read_root():
    return {"message": "Hello, World!"}
