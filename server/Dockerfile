FROM python:3.10-slim 
RUN pip install flask
COPY server.py .
EXPOSE 5000
CMD ["python", "server.py"]