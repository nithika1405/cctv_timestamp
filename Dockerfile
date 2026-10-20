FROM python:3.10-slim

# Install system dependencies for OpenCV and other packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Copy dependency spec first (Docker layer caching)
COPY pyproject.toml /app/
COPY src/ /app/src/

# Install the project and its dependencies
RUN pip install --no-cache-dir -e .

# Copy the rest of the application
COPY . /app/

# Create a non-root user
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Expose the FastAPI backend; React is served by the frontend container.
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Run the API used by the React frontend
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
