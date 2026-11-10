FROM ubuntu:latest

COPY ipv64-ipv64-ddns-update_0.2-1_all.deb /tmp/ipv64-ipv64-ddns-update_0.2-1_all.deb

RUN <<EOF
    export DEBIAN_FRONTEND=noninteractive &&
    apt update &&
    apt install -y dnsutils curl jq adduser &&
    dpkg -i /tmp/ipv64-ipv64-ddns-update_0.2-1_all.deb &&
    mkdir /var/log/ipv64-ddns-update &&
    rm /tmp/ipv64-ipv64-ddns-update_0.2-1_all.deb
    apt clean
EOF