# /worker/Dockerfile

# Use a lightweight Python image
FROM python:3.10-slim
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual Python script
COPY main.py .

# Run the worker
CMD ["python", "-u", "main.py"] 
# (The -u flag forces Python to print logs to the terminal instantly)