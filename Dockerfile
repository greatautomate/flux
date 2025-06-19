# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1    PYTHONUNBUFFERED=1    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y    gcc    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip &&    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' botuser &&    chown -R botuser:botuser /app
USER botuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3    CMD python -c "import requests; requests.get('https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe', timeout=5)" || exit 1

# Run the application
CMD ["python", "main.py"]
