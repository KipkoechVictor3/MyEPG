# Base image with Python
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libasound2 \
    libnss3 \
    libxss1 \
    libxshmfence1 \
    libgbm1 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy files
COPY . .

# Install Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Install Firefox via Playwright
RUN playwright install --with-deps firefox

# Run script on container start
CMD ["python", "main.py"]
