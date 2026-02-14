# backend/Dockerfile

# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Safety measures (env vars)
#   - PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files (no need in containers)
#   - PYTHONUNBUFFERED: Ensure logs appear instantly in terminal
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System Dependencies (Important for Postgres)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists*

# Install poetry
RUN pip install poetry

# Set the working directory in the container
WORKDIR /app

# Copy only the files needed for dependency installation
COPY pyproject.toml poetry.lock ./

# Install project dependencies
#   - --no-root: don't install the project as a package
#   - --only-main: skip dev dependencies
RUN poetry config virtualenvs.create false \
     && poetry install --no-root --only main --no-interaction --no-ansi

# Copy the rest of the application code into the container
COPY . .

# Command to run the application
# For now, keep reload to avoid having to restart the container while building features
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]