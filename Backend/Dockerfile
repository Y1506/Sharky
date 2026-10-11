FROM python:3.12-slim

# Install system dependencies: aria2 for accelerated downloads, ffmpeg for media processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    aria2 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application package
COPY download_manager/ ./download_manager/

# Create downloads volume mount point
VOLUME /downloads

# Ensure Python output is unbuffered for real-time logging
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "download_manager"]
