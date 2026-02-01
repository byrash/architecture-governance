# Architecture Governance Container
# Lightweight container with Python + Node.js for Copilot CLI
FROM python:3.11-slim

LABEL maintainer="Architecture Governance"
LABEL description="Lightweight container for architecture governance validation using GitHub Copilot"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    jq \
    ca-certificates \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 LTS (ignore SSL for corporate proxies/self-signed certs)
RUN curl -fsSL --insecure https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Configure npm and git to allow self-signed certificates
RUN npm config set strict-ssl false \
    && git config --global http.sslVerify false

# Install GitHub Copilot CLI
RUN npm install -g @github/copilot

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies (ignore SSL)
COPY requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -r requirements.txt

# Copy application files
COPY copilot/ ./copilot/
COPY governance/ ./governance/
COPY entrypoint.sh ./

# Make entrypoint executable
RUN chmod +x entrypoint.sh

# Create output directory
RUN mkdir -p governance/output

# Environment variables (CONFLUENCE_URL, CONFLUENCE_API_TOKEN, PAGE_ID passed at runtime)
ENV PYTHONUNBUFFERED=1

# SSL/TLS - Allow self-signed certificates
ENV NODE_TLS_REJECT_UNAUTHORIZED=0
ENV PYTHONHTTPSVERIFY=0
ENV GIT_SSL_NO_VERIFY=1
ENV CURL_CA_BUNDLE=""
ENV REQUESTS_CA_BUNDLE=""
ENV SSL_CERT_FILE=""

# Entrypoint constructs .github and runs governance
ENTRYPOINT ["./entrypoint.sh"]

# Default command - ingest Confluence page
CMD ["ingest"]
