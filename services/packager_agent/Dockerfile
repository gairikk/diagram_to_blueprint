FROM python:3.11-slim
WORKDIR /app

COPY shared /app/shared
COPY services/packager_agent /app/services/packager_agent

RUN pip install --no-cache-dir -r /app/shared/requirements.txt

ENV PYTHONPATH=/app
ENV RUNS_DIR=/app/runs
EXPOSE 8000

CMD ["uvicorn", "services.packager_agent.app.main:app", "--host", "0.0.0.0", "--port", "8000"]