# Toss CLI — multi-platform Docker image
#
# Build:
#   docker build -t toss .
#
# Usage:
#   docker run --rm -v ~/.toss:/root/.toss -v $(pwd):/work toss push report.md xiaoming
#   docker run --rm -v ~/.toss:/root/.toss -v $(pwd):/work toss pull
#
# Alias (add to ~/.bashrc or ~/.zshrc):
#   alias toss='docker run --rm -v ~/.toss:/root/.toss -v $(pwd):/work toss'
#
FROM python:3.13-slim

LABEL maintainer="Han Haoke <hanhaoke@qdu.edu.cn>"
LABEL description="Toss: CLI tool for sharing AI-generated artifacts"

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install the package
RUN uv pip install --system --no-cache .

# Working directory for file operations
WORKDIR /work

ENTRYPOINT ["toss"]
CMD ["--help"]
