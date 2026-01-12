FROM python:3.12-slim

# Metadata
LABEL maintainer="Bini Python Upgrade Analyzer"
LABEL version="1.1.0"
LABEL description="Python version upgrade compatibility analyzer with LLM validation"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Install Bini as a package
RUN pip install --no-cache-dir -e .

# Create output and workspace directories
RUN mkdir -p /output /workspace

# Set up volumes
VOLUME ["/workspace", "/output"]

# Set default working directory to workspace
WORKDIR /workspace

# Default environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OLLAMA_HOST=http://ollama:11434

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD bini-analyzer --version || exit 1

# Entrypoint
ENTRYPOINT ["bini-analyzer"]

# Default command (can be overridden)
CMD ["--help"]
