# frontend/Dockerfile

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

# Expose the port
#  - Streamlit runs on 8501 by default
EXPOSE 8501

# Run Streamlit
#   - --server.port=8501: forces the port
#   - --server.address=0.0.0.0 : very important for Docker as we are telling it
# to accept connections from outside the container.
CMD ["streamlit", "run", "1_Tracker_&_Dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
