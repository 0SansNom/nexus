FROM python:3.12-slim

WORKDIR /app

# Install build dependencies for chromadb
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install requirements
COPY memory_agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code
COPY shared ./shared

# Copy agent code
COPY memory_agent/*.py ./

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user
RUN useradd -m -u 1000 nexus && \
    mkdir -p /data && \
    chown -R nexus:nexus /app /data
USER nexus

# Run agent
CMD ["python", "main.py"]
