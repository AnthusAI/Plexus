FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/private-graphql-proxy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY services/private-graphql-proxy/proxy ./proxy

EXPOSE 8000
CMD ["uvicorn", "proxy.app:app", "--host", "0.0.0.0", "--port", "8000"]
