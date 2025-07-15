# Use an official Python runtime as a parent image
FROM python:3.9-slim-bullseye

# Install sqlite3-specific packages for database checks
RUN apt-get update && apt-get install -y sqlite3 --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly copy the docker-entrypoint.sh script and make it executable.
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# Add a debug step: List files and permissions in /app
RUN ls -la /app

# Copy the rest of the application code into the container at /app
COPY . .

# Create necessary directories for data and logs INSIDE the container
RUN mkdir -p data/raw data/raw_aapl

# Expose the port that FastAPI will run on
EXPOSE 8000

# --- START OF FINAL ENTRYPOINT CHANGE ---
# Execute the script directly with /bin/sh. This directly runs the script
# using sh, bypassing any shebang interpretation issues.
ENTRYPOINT ["/bin/sh", "./docker-entrypoint.sh"]
# --- END OF FINAL ENTRYPOINT CHANGE ---

# Default command if no arguments are provided to ENTRYPOINT (can be empty if entrypoint runs everything)
CMD []