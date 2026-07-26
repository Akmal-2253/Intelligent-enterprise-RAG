FROM python:3.12-slim

WORKDIR /app

# gcc + libpq-dev: needed to build psycopg2 from source on slim images.
# Removed after install (apt cache) to keep the image smaller.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# These get overridden by volume mounts in docker-compose.yml, but
# creating them here means the container still works standalone
# (`docker run`) without the volumes attached.
RUN mkdir -p documents faiss_index

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]