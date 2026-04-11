FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Hugging Face Spaces runs as non-root user 1000
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 7860

CMD ["gunicorn", "wsgi:server", "--bind", "0.0.0.0:7860", "--workers", "2", "--timeout", "120"]
