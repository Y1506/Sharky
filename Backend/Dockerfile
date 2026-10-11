FROM python:3.12-slim

# Install system dependencies: aria2 for accelerated downloads, ffmpeg for media processing, curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    aria2 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application package and runner
COPY run.py .
COPY download_manager/ ./download_manager/

# Create downloads volume mount point
RUN mkdir -p /downloads
VOLUME /downloads

# Configuration environment variables
ENV PYTHONUNBUFFERED=1 \
    DOWNLOAD_DIR=/downloads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["python", "run.py"]
CMD ["server"]
