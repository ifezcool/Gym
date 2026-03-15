FROM python:3.12-slim

# Install system dependencies needed for pyodbc / ODBC Driver 17
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    libgssapi-krb5-2 \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/12/prod.list \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY pages/ ./pages/

# Copy any static assets referenced in the code
COPY wellness_image_1.png .
COPY GymPortal.png .
COPY ["Ladol Special Wellness.csv", "."]

EXPOSE 8050

# Use gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "--timeout", "120", "app:server"]