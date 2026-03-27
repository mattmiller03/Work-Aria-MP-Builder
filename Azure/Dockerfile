FROM python:3.11-slim

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app/ /adapter
WORKDIR /adapter

ENTRYPOINT ["python", "adapter.py"]
