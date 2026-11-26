FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY afm_pathological/ afm_pathological/
COPY main.py .
CMD ["python", "main.py"]
