FROM python:3.10-slim

RUN apt-get update && apt-get install -y docker.io sudo && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install flask requests
COPY . .

EXPOSE 5000
CMD ["python", "lb.py"]