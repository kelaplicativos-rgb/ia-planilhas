
FROM python:3.10-slim

# ============================================================
# SISTEMA (OBRIGATÓRIO PARA PLAYWRIGHT)
# ============================================================

RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libatspi2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxrender1 \
    libxshmfence1 \
    libglib2.0-0 \
    libdbus-1-3 \
    libgtk-3-0 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
# PYTHON
# ============================================================

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# ============================================================
# PLAYWRIGHT (CRÍTICO)
# ============================================================

RUN python -m playwright install --with-deps chromium

# ============================================================
# APP
# ============================================================

COPY . .

# ============================================================
# STREAMLIT
# ============================================================

ENV PORT=8501
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
