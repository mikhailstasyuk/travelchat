from fastapi import FastAPI

from .api.v1.endpoints import ping as ping_router_v1

app = FastAPI()

app.include_router(ping_router_v1.router, prefix="/api/v1", tags=["v1"])
