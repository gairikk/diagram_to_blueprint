FROM python:3.11-slim

WORKDIR /app

# Copy shared libs and the graph service code
COPY shared /app/shared
COPY services/graph_agent /app/services/graph_agent

# Install dependencies (shared requirements)
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

# Make "shared" and "services" importable
ENV PYTHONPATH=/app
ENV RUNS_DIR=/app/runs

EXPOSE 8000

CMD ["uvicorn", "services.graph_agent.app.main:app", "--host", "0.0.0.0", "--port", "8000"]