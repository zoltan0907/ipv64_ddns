#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
import json

CONFIG_FILE = os.getenv("CONFIG_FILE", "/etc/ipv64-ddns-update/config.cfg")
NAMESERVER = "ns1.ipv64.net"

def load_config():
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

def get_ip(interface, record_type):
    target_family = "inet6" if record_type == "AAAA" else "inet"
    try:
        cmd = ["ip", "-j", "addr", "show", "dev", interface]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
        if not data: return None
            
        for addr in data[0].get("addr_info", []):
            if addr.get("family") == target_family:
                ip = addr.get("local")
                if target_family == "inet6" and ip.startswith("fe80:"):
                    continue
                return ip
    except Exception as e:
        print(f"Fehler bei IP-Ermittlung: {e}")
    return None

def get_current_dns_value(fqdn, record_type):
    """Fragt den aktuellen Wert direkt bei ns1.ipv64.net ab."""
    try:
        # +short gibt nur die reinen Werte (z.B. IPs oder Strings) ohne Overhead zurück
        cmd = ["dig", f"@{NAMESERVER}", fqdn, "-t", record_type, "+short"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Anführungszeichen entfernen, die dig bei TXT-Records hinzufügt
        lines = [line.strip().strip('"') for line in res.stdout.splitlines() if line.strip()]
        return lines
    except FileNotFoundError:
        print("Fehler: 'dig' Befehl fehlt. Bitte installiere dnsutils oder bind-tools im Container.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        return []

def update_dyndns_a_aaaa(token, fqdn, ip, record_type):
    params = {"key": token, "domain": fqdn}
    if record_type == "AAAA":
        params["ip6"] = ip
    else:
        params["ip"] = ip
        
    url = f"https://ipv64.net/nic/update?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as resp:
            answer = resp.read().decode('utf-8').strip()
            print(f"IPv64.net DDNS Antwort: {answer}")
            return "good" in answer or "nochg" in answer
    except Exception as e:
        print(f"Fehler beim IPv64 Update: {e}")
        return False

def update_api_record(token, domain, prefix, content, record_type):
    url = "https://ipv64.net/api.php"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "add_record": domain,
        "praefix": prefix,
        "type": record_type,
        "content": content
    }
    encoded = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request(url, data=encoded, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as resp:
            answer = resp.read().decode('utf-8').strip()
            print(f"IPv64.net API Antwort: {answer}")
            return True
    except Exception as e:
        print(f"Fehler beim Update via API: {e}")
        return False

def main():
    load_config()
    
    interface = os.getenv("INTERFACE_NAME", "eth0")
    record_type = os.getenv("RECORD_TYPE", "A").upper()
    token = os.getenv("IPV64_TOKEN")
    domain = os.getenv("IPV64_DOMAIN")
    prefix = os.getenv("IPV64_PREFIX", "")
    interval = int(os.getenv("UPDATE_INTERVAL", "300")) # Standard: 5 Minuten
    
    if not token or not domain:
        print("Fehler: IPV64_TOKEN und IPV64_DOMAIN müssen gesetzt sein.")
        sys.exit(1)

    fqdn = f"{prefix}.{domain}" if prefix else domain

    print(f"Starte DDNS Updater. Intervall: {interval} Sekunden. FQDN: {fqdn}")
    
    while True:
        ip = get_ip(interface, record_type)
        
        if not ip:
            print(f"Keine IP auf Interface {interface} gefunden.")
        else:
            current_dns_values = get_current_dns_value(fqdn, record_type)
            
            if ip in current_dns_values:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] DNS ist bereits aktuell (IP: {ip}). Keine Aktion nötig.")
            else:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] IP-Änderung erkannt: '{ip}' (Aktuell im DNS: {current_dns_values})")
                print(f"Führe Update für {fqdn} durch...")
                
                if record_type in ["A", "AAAA"]:
                    update_dyndns_a_aaaa(token, fqdn, ip, record_type)
                else:
                    update_api_record(token, domain, prefix, ip, record_type)
        
        time.sleep(interval)

if __name__ == "__main__":
    main()