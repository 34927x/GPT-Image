# Use official Playwright Python image which has all browser dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Set work directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements-local.txt .
RUN pip install --no-cache-dir -r requirements-local.txt

# Copy the rest of the application files
COPY . .

# Expose the worker port
EXPOSE 8888

# Start the worker
CMD ["python3", "local_worker.py"]
