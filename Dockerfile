# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy the entire repository (GLIA core + hackathon folder)
COPY . /app

# Install GLIA engine in editable mode (found in the root)
RUN pip install -e .

# Install hackathon specific requirements
RUN pip install --no-cache-dir -r hackathon/requirements.txt

# Set the working directory to the hackathon folder for execution
WORKDIR /app/hackathon

# Expose port (Cloud Run uses 8080 by default)
EXPOSE 8080

# Command to run the FastAPI server
CMD ["python", "main.py"]
