FROM python:3.11-slim

WORKDIR /app

ARG INSTALL_CALIBRE=0

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN if [ "$INSTALL_CALIBRE" = "1" ]; then \
      apt-get update && \
      apt-get install -y --no-install-recommends calibre && \
      rm -rf /var/lib/apt/lists/*; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "manage:app"]
