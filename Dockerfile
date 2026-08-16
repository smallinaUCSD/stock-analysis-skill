# Production image — serves the PUBLIC (safe, read-only) stockskill dashboard.
# Holdings and watchlist-mutation routes are NOT registered in public mode, and
# holdings.csv is excluded from the image (.dockerignore).
FROM python:3.12-slim

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY . .
RUN uv sync --frozen --no-dev --group deploy

# Safe shared mode (see create_app / DEPLOYMENT.md). Override BMC via the host env.
ENV STOCKSKILL_PUBLIC=1
ENV PYTHONUNBUFFERED=1

# The host injects $PORT. One worker (shares the board cache) with threads so
# API calls aren't blocked while the board refetches.
CMD ["sh", "-c", "uv run gunicorn -w 1 -k gthread --threads 8 -t 120 -b 0.0.0.0:${PORT:-8000} 'stockskill.server:create_app()'"]
