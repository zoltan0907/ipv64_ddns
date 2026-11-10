#!/usr/bin/env python3
import os
import sys
import subprocess
import urllib.request
import urllib.parse
import json

# Fallback auf Standard-Pfad wie im originalen Container
CONFIG_FILE = os.getenv("CONFIG_FILE", "/etc/ipv64-ddns-update/config.cfg")

def load_config():
    """Liest die .cfg Datei ein und exportiert sie als Umgebungsvariablen."""
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                # Kommentare und Leerzeilen ignorieren
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k.strip(), v.strip())

def get_ip(interface, record_type):
    """Holt die IP direkt vom Interface mittels 'ip -j' und parst das JSON."""
    # JSON von iproute2 nutzt "inet" für IPv4 und "inet6" für IPv6
    target_family = "inet6" if record_type == "AAAA" else "inet"
    
    try:
        cmd = ["ip", "-j", "addr", "show", "dev", interface]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        data = json.loads(res.stdout)
        if not data:
            return None
            
        # Wir durchsuchen die addr_info des abgefragten Interfaces
        for addr in data[0].get("addr_info", []):
            if addr.get("family") == target_family:
                ip = addr.get("local")
                
                # Link-lokale fe80 IPv6-Adressen ignorieren
                if target_family == "inet6" and ip.startswith("fe80:"):
                    continue
                    
                return ip
                
    except FileNotFoundError:
        print("Fehler: 'ip' Befehl fehlt. Stelle sicher, dass 'iproute2' installiert ist.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print(f"Fehler: Interface '{interface}' konnte nicht abgefragt werden.")
    except json.JSONDecodeError:
        print("Fehler: Konnte die JSON-Ausgabe von 'ip' nicht parsen.")
        
    return None

def check_cache(domain, prefix, record_type, ip):
    """Prüft, ob die IP bereits upgedatet wurde, um API-Limits zu schonen."""
    cache_path = f"/tmp/ipv64_{domain}_{prefix}_{record_type}.cache"
    if os.path.isfile(cache_path):
        with open(cache_path, "r") as f:
            if f.read().strip() == ip:
                return True, cache_path
    return False, cache_path

def update_dyndns_a_aaaa(token, domain, prefix, ip, record_type):
    """Nutzt die native Update-URL, die bestehende Records sauber überschreibt."""
    hostname = f"{prefix}.{domain}" if prefix else domain
    params = {"key": token, "domain": hostname}
    
    if record_type == "AAAA":
        params["ip6"] = ip
    else:
        params["ip"] = ip
        
    url = f"https://ipv64.net/nic/update?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req) as resp:
            answer = resp.read().decode('utf-8').strip()
            print(f"IPv64.net DDNS Antwort: {answer}")
            return "good" in answer or "nochg" in answer
    except Exception as e:
        print(f"Fehler beim IPv64 Update: {e}")
        return False

def update_api_record(token, domain, prefix, content, record_type):
    """Nutzt die REST-API, um andere Record-Typen (TXT, SRV etc.) zu setzen."""
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
    
    # Variablen einlesen (ENV hat Vorrang, danach Config-Datei)
    interface = os.getenv("INTERFACE_NAME", "eth0")
    record_type = os.getenv("RECORD_TYPE", "A").upper()
    token = os.getenv("IPV64_TOKEN")
    domain = os.getenv("IPV64_DOMAIN")
    prefix = os.getenv("IPV64_PREFIX", "")
    
    if not token or not domain:
        print("Fehler: IPV64_TOKEN und IPV64_DOMAIN müssen gesetzt sein.")
        sys.exit(1)
        
    print(f"Prüfe IP auf Interface '{interface}' für Record-Typ '{record_type}'...")
    ip = get_ip(interface, record_type)
    
    if not ip:
        print(f"Keine IP auf Interface {interface} gefunden. Abbruch.")
        sys.exit(1)
        
    print(f"Gefundene IP: {ip}")
    
    # Cache prüfen, damit wir die API nicht spammen, wenn sich nichts ändert
    is_cached, cache_path = check_cache(domain, prefix, record_type, ip)
    if is_cached:
        print("IP ist unverändert. Kein API-Update nötig.")
        sys.exit(0)
        
    print(f"Übermittle Record {prefix + '.' if prefix else ''}{domain} an IPv64.net...")
    
    # Update Logik
    success = False
    if record_type in ["A", "AAAA"]:
        success = update_dyndns_a_aaaa(token, domain, prefix, ip, record_type)
    else:
        # Für TXT, SRV, CNAME etc. muss die API verwendet werden
        success = update_api_record(token, domain, prefix, ip, record_type)
        
    # Wenn Update erfolgreich war, aktualisiere den Cache
    if success:
        with open(cache_path, "w") as f:
            f.write(ip)
        print("Update erfolgreich. Cache wurde geschrieben.")
    else:
        print("Update fehlgeschlagen, Cache wurde nicht aktualisiert.")
        sys.exit(1)

if __name__ == "__main__":
    main()