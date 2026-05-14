FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=6 \
    MKL_NUM_THREADS=6

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8866

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8866"]
