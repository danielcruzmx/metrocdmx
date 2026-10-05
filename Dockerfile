# 1. Usamos una imagen base que ya incluye SWI-Prolog estable
FROM swipl:stable

# 2. Instalamos Python y herramientas necesarias del sistema
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    && rm -rf /var/lib/apt/lists/*

# 3. Configurar directorio de trabajo
WORKDIR /app

# 4. Copiar archivos del proyecto
COPY . /app

# 5. Instalar las dependencias de Python
RUN pip3 install --no-cache-dir fastapi uvicorn swiplserver pydantic --break-system-packages

# 6. Exponer el puerto de FastAPI
EXPOSE 8070

# 7. Arrancar FastAPI con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8070"]
