FROM python:3.11-slim

WORKDIR /app

# Copy shared libs and the parser service code
COPY shared /app/shared
COPY services/parser_agent /app/services/parser_agent

# Install dependencies (shared requirements)
RUN pip install --no-cache-dir -r /app/shared/requirements.txt

# Set python path so "shared" and "services" are importable
ENV PYTHONPATH=/app
ENV RUNS_DIR=/app/runs

EXPOSE 8000

CMD ["uvicorn", "services.parser_agent.app.main:app", "--host", "0.0.0.0", "--port", "8000"]