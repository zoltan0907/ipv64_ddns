FROM ubuntu:latest

COPY ipv64-ddns-update /usr/local/bin

RUN <<EOF
    export DEBIAN_FRONTEND=noninteractive &&
    apt update &&
    apt install -y dnsutils curl jq adduser &&
    mkdir /var/log/ipv64-ddns-update &&
    apt clean
EOF