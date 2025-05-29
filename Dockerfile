# Use official Python 3.10 image to match local environment
FROM python:3.10-alpine

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    libopenblas-dev \
    libomp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu

# Copy Django project files
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose Django port
EXPOSE 8000

# Run with Gunicorn
CMD ["gunicorn", "Ala_Django.wsgi:application", "--bind", "0.0.0.0:8000"]