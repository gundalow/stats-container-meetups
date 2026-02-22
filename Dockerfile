FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libfreetype6-dev \
    libpng-dev \
    libopenjp2-7-dev \
    libtiff5-dev \
    libxcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY meetup_bot.py .

RUN mkdir -p /srv/docker-config/meetup /srv/docker-pins/meetup

ENTRYPOINT ["python", "meetup_bot.py"]
CMD ["--help"]
