FROM python:alpine

RUN apk update && apk add git
RUN git clone https://github.com/bowerscd/dashboard-client.git /aoe2dashboard
RUN pip install /aoe2dashboard
RUN apk del git

ADD . /app/
WORKDIR /app/

RUN pip install -r requirements.txt

ENTRYPOINT [ "python", "/app/__main__.py" ]