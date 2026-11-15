FROM python:3.12.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY models/manifest.json models/manifest.json
COPY scripts/download_model.py scripts/download_model.py
RUN python scripts/download_model.py
COPY rooftrace rooftrace
COPY app.py .
COPY static static
RUN useradd --create-home rooftrace
USER rooftrace
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
