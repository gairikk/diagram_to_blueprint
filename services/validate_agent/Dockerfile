FROM python:3.11-slim
WORKDIR /app

# OS deps for downloads/unzip
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform
ARG TF_VERSION=1.7.5
RUN curl -fsSL https://releases.hashicorp.com/terraform/${TF_VERSION}/terraform_${TF_VERSION}_linux_amd64.zip -o /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip

# Install TFLint
ARG TFLINT_VERSION=0.53.0
RUN curl -fsSL https://github.com/terraform-linters/tflint/releases/download/v${TFLINT_VERSION}/tflint_linux_amd64.zip -o /tmp/tflint.zip \
    && unzip /tmp/tflint.zip -d /usr/local/bin \
    && rm /tmp/tflint.zip

# Install Checkov (python)
RUN pip install --no-cache-dir checkov==3.2.317

COPY shared /app/shared
COPY services/validate_agent /app/services/validate_agent

RUN pip install --no-cache-dir -r /app/shared/requirements.txt

ENV PYTHONPATH=/app
ENV RUNS_DIR=/app/runs
EXPOSE 8000

CMD ["uvicorn", "services.validate_agent.app.main:app", "--host", "0.0.0.0", "--port", "8000"]