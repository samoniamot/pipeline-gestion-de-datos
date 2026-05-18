FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py ingesta.py limpieza.py validacion.py carga.py ./
COPY origen/ origen/
COPY templates/ templates/

RUN mkdir -p data/raw data/processed data/validated data/invalid logs

EXPOSE 5000

CMD ["python", "app.py"]
