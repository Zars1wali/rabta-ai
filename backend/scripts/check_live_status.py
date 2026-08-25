import urllib.request
import json

def main():
    print("=" * 75)
    print("RABTA AI — LIVE HAIDER ARMS SYSTEM HEALTH CHECK")
    print("=" * 75)

    # 1. Check FastAPI Backend
    try:
        req = urllib.request.urlopen("http://127.0.0.1:8000/api/business/923040124445", timeout=5)
        biz = json.loads(req.read().decode())
        print("[+] FastAPI Backend (Port 8000): ONLINE")
        print(f"    - Tenant: {biz.get('name')}")
        print(f"    - Phone: {biz.get('business_phone')}")
        print(f"    - Catalog Items in PostgreSQL: {len(biz.get('catalog', []))}")
    except Exception as e:
        print(f"[-] FastAPI Backend: ERROR -> {e}")

    # 2. Check Baileys WhatsApp Gateway
    try:
        req2 = urllib.request.urlopen("http://127.0.0.1:3001/qr", timeout=5)
        gw = json.loads(req2.read().decode())
        print("\n[+] Baileys WhatsApp Gateway (Port 3001): ONLINE")
        print(f"    - Gateway Connection Status: {gw.get('status')}")
        print(f"    - Connected WhatsApp Number: +{gw.get('connected_number')}")
    except Exception as e:
        print(f"[-] WhatsApp Gateway: ERROR -> {e}")

    # 3. Live End-to-End Chat Test via Gateway Bridge
    try:
        payload = json.dumps({
            "customer_phone": "923001234567",
            "business_phone": "923040124445",
            "message": "Glock 19X hai apke pass aur rate kya hai?"
        }).encode("utf-8")

        req3 = urllib.request.Request(
            "http://127.0.0.1:8000/api/gateway/process-message",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        res3 = json.loads(urllib.request.urlopen(req3, timeout=20).read().decode())
        print("\n[+] Live End-to-End Chat Test:")
        print(f"    - Customer Query: 'Glock 19X hai apke pass aur rate kya hai?'")
        print(f"    - Store AI Reply: \"{res3.get('reply')}\"")
        print(f"    - Response Latency: {res3.get('latency_ms')}ms")
    except Exception as e:
        print(f"[-] Live Chat Test: ERROR -> {e}")

    print("\n" + "=" * 75)


if __name__ == "__main__":
    main()
