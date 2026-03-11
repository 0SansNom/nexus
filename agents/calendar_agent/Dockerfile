FROM python:3.12-slim

WORKDIR /app

# Copy and install requirements
COPY calendar_agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared code
COPY shared ./shared

# Copy agent code
COPY calendar_agent/*.py ./

# Set Python path
ENV PYTHONPATH=/app

# Create non-root user
RUN useradd -m -u 1000 nexus && chown -R nexus:nexus /app
USER nexus

# Run agent
CMD ["python", "main.py"]
