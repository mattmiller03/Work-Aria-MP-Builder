FROM python:3.11-slim

COPY app/wheels/ /tmp/wheels/
RUN pip install --no-cache-dir --no-index --find-links /tmp/wheels/ -r /tmp/wheels/requirements.txt && rm -rf /tmp/wheels

COPY app/ /adapter
WORKDIR /adapter

ENTRYPOINT ["python", "adapter.py"]
