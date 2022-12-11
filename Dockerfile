FROM python:alpine

ADD . /app/
WORKDIR /app/

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "/app/main.py", "-b" ]