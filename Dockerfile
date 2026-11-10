FROM python:alpine

RUN apk add --no-cache iproute2

WORKDIR /usr/src/app

COPY ipv64-ddns-update.py .

CMD [ "python", "ipv64-ddns-update.py" ]