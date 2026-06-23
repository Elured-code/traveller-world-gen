FROM python:3.11-slim

WORKDIR /app

# Install FastAPI dependencies first for layer caching
COPY fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install traveller-gen package (no deps — already installed above)
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --no-deps .

# FastAPI app (app.py, helpers.py, static/)
COPY fastapi/ ./fastapi/

# helpers.py is flat inside fastapi/ (not a package) — add to PYTHONPATH
ENV PYTHONPATH=/app/fastapi

WORKDIR /app/fastapi

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
