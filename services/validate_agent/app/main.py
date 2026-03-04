from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.validate_agent.app.handler import run_step

app = FastAPI(title="validate_agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/run")
def run(envelope: dict):
    return run_step(envelope)