import sys
sys.path.insert(0, '/opt/xhttp-manager/addon')
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import users, config, stats, system
from db.database import init_db

app = FastAPI(title="xhttp-manager", version="1.0.0")

@app.on_event("startup")
def startup():
    init_db()

app.include_router(users.router)
app.include_router(config.router)
app.include_router(stats.router)
app.include_router(system.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
