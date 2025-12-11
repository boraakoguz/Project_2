FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make scripts executable
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 5001

# Set entrypoint
ENTRYPOINT ["bash", "/app/entrypoint.sh"]

# Run the application
CMD ["python3", "marketing_automation.py"]
