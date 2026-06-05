FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Keep setuptools compatible for whisper build tooling (pkg_resources)
RUN python -m pip install --upgrade pip wheel "setuptools<81"

# Install whisper first in non-isolated mode
RUN pip install --no-cache-dir --no-build-isolation openai-whisper

# Install remaining dependencies
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.baseUrlPath=streamlit-app"]
