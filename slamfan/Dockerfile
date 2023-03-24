FROM python:alpine

ADD . /app/
WORKDIR /app/

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "/app/__main__.py" ]