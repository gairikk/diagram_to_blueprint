from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services.normalizer_agent.app.handler import run_step

app = FastAPI(title="normalizer_agent")

app.add_middleware(
    CORSMiddleware,
        allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/run")
def run(envelope: dict):
    return run_step(envelope)