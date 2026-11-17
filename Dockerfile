FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080 DB_PATH=/data/ai_quant_x.db
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# VADER lexicon for the (optional) news-sentiment filter; if the download fails the filter reports "unavailable".
RUN python -c "import nltk; nltk.download('vader_lexicon', download_dir='/usr/share/nltk_data')" || true
COPY . .
# Runs as root on purpose: a Railway volume mounted on /data is owned by root and a non-root user could not write
# the database there. The container exposes only the dashboard port and holds no exchange credentials.
RUN mkdir -p /data
EXPOSE 8080
# Railway also performs its own check (railway.toml); this one makes `docker run` self-diagnosing.
HEALTHCHECK --interval=60s --timeout=10s --start-period=90s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8080')+'/health',timeout=8)" || exit 1
STOPSIGNAL SIGTERM
CMD ["python", "main.py"]
