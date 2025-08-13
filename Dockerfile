# Dockerfile for FastAPI Allergy Scanner
# - Uses lightweight Python base image
# - Installs system dependency for pyzbar (libzbar0)
# - Installs Python dependencies
# - Copies app code and runs with uvicorn

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libzbar0 \
       curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (leverages Docker layer caching)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Expose application port
EXPOSE 8000

# Default command runs the FastAPI app using uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

