# --- builder ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --upgrade pip build && pip install '.[dev]'

# --- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# non-root user
RUN groupadd --system app && useradd --system --create-home --gid app app

WORKDIR /app

# copy installed site-packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY --from=builder /usr/local/bin/agentic-onboard /usr/local/bin/agentic-onboard
COPY --from=builder /usr/local/bin/mock-crm /usr/local/bin/mock-crm
COPY --from=builder /app/src /app/src

USER app

EXPOSE 8765

# default command runs the mock CRM. Override for the orchestrator.
CMD ["uvicorn", "mock_crm.server:app", "--host", "0.0.0.0", "--port", "8765"]
