FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY fastapi/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Root-level generator modules
COPY html_render.py \
     system_map.py \
     system_pipeline.py \
     tables.py \
     traveller_belt_physical.py \
     traveller_hydro_detail.py \
     traveller_map_fetch.py \
     traveller_moon_gen.py \
     traveller_orbit_gen.py \
     traveller_stellar_gen.py \
     traveller_system_gen.py \
     traveller_world_atmosphere_detail.py \
     traveller_world_detail.py \
     traveller_world_gen.py \
     traveller_world_government_detail.py \
     traveller_world_law_detail.py \
     traveller_world_physical.py \
     traveller_world_population_detail.py \
     traveller_world_schema.json \
     traveller_world_tech_detail.py \
     world_codes.py \
     ./

# templates/ must sit next to html_render.py — html_render.py resolves it as
# Path(__file__).parent / "templates", so /app/templates/ is the required path.
COPY templates/ ./templates/

# FastAPI app (app.py, helpers.py, static/)
COPY fastapi/ ./fastapi/

# /app for root modules; /app/fastapi for helpers.py (flat, not in a package)
ENV PYTHONPATH=/app:/app/fastapi

WORKDIR /app/fastapi

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
