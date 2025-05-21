from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def read_ping():
    return {"ping": "pong"}
