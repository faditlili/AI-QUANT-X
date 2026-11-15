FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import nltk; nltk.download('vader_lexicon', download_dir='/usr/share/nltk_data')" || true
COPY . .
# Runs as root on purpose: a Railway volume mounted on /data is owned by root,
# and a non-root user could not write the database there.
RUN mkdir -p /data
EXPOSE 8080
CMD ["python", "main.py"]
