FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MCP_HOST=0.0.0.0 \
    MCP_TRANSPORT=streamable-http \
    MCP_HTTP_PATH=/mcp \
    BROWSER_PATH=/usr/bin/chromium

# Chromium is used by Kaleido to export the PNG that the MCP tool returns.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["python", "-m", "social_analytics_mcp"]
