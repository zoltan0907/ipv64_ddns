FROM python:alpine

WORKDIR /usr/src/app

COPY ipv64-ddns-update.py .

CMD [ "python", "ipv64-ddns-update.py" ]