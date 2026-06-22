import os
import sys

# Add Backend to python path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "Backend"))

try:
    from api.twilio_dispatch import send_sms, send_whatsapp, is_twilio_configured
except ImportError as e:
    print(f"Error importing twilio_dispatch: {e}")
    sys.exit(1)

def load_config():
    config = {}
    
    # 1. Try reading from .streamlit/secrets.toml
    toml_path = os.path.join(BASE_DIR, ".streamlit", "secrets.toml")
    if os.path.exists(toml_path):
        with open(toml_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    config[k] = v

    # 2. Try reading from .env
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    config[k] = v

    # 3. Check os.environ
    keys = ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM_PHONE", "TWILIO_TO_PHONE", "TWILIO_WHATSAPP_FROM"]
    for k in keys:
        if k in os.environ and os.environ[k]:
            config[k] = os.environ[k]
            
    return config

def main():
    print("=" * 60)
    print("        GridLock AI — Twilio Integration Tester")
    print("=" * 60)
    
    # Load and set config into environment variables for twilio_dispatch to read
    config = load_config()
    for k, v in config.items():
        os.environ[k] = v
        
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_phone = os.environ.get("TWILIO_FROM_PHONE", "")
    to_phone = os.environ.get("TWILIO_TO_PHONE", "")
    whatsapp_from = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    
    # Mask token for print
    masked_token = (token[:6] + "..." + token[-6:]) if len(token) > 12 else "NOT_SET"
    
    print(f"Twilio Configuration Status:")
    print(f"  - Account SID:   {sid or 'NOT_SET'}")
    print(f"  - Auth Token:    {masked_token}")
    print(f"  - From Phone:    {from_phone or 'NOT_SET'}")
    print(f"  - To Phone:      {to_phone or 'NOT_SET'}")
    print(f"  - WhatsApp From: {whatsapp_from}")
    print("-" * 60)

    # Check if dependencies are installed
    try:
        import twilio
        print("✅ twilio python package is installed.")
    except ImportError:
        print("❌ twilio package is NOT installed. Please run: pip install twilio")
        return

    # Check config validity
    if not sid or not token:
        print("\n⚠️  WARNING: Twilio credentials are not set!")
        print("To configure, you can either:")
        print("1. Create `.streamlit/secrets.toml` in your project folder with these contents:")
        print("   TWILIO_ACCOUNT_SID = \"your_sid_here\"")
        print("   TWILIO_AUTH_TOKEN = \"your_token_here\"")
        print("   TWILIO_FROM_PHONE = \"+1234567890\"")
        print("   TWILIO_TO_PHONE = \"+91XXXXXXXXXX\"")
        print("   TWILIO_WHATSAPP_FROM = \"whatsapp:+14155238886\"")
        print("\n2. Or add them to your `.env` file in the root folder.")
        print("\nRunning in DEMO MODE (simulating dispatch)...")
    else:
        print("\n✅ Credentials found! Running in LIVE MODE.")

    # Sample data for test message
    zone_id = "Z_TEST_99"
    severity = "CRITICAL"
    impact_score = 0.8924
    risk_score = 0.9412
    center_lat = 12.9716
    center_lng = 77.5946
    action = "Dispatch Tow Truck ASAP"

    print("\nSelect test channel:")
    print("  1. Send Test SMS")
    print("  2. Send Test WhatsApp")
    print("  3. Exit")
    
    try:
        choice = input("\nEnter choice (1/2/3): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nExiting.")
        return

    if choice == '1':
        print(f"\nSending SMS to {to_phone or 'Demo Number'}...")
        success, response = send_sms(
            zone_id=zone_id,
            severity=severity,
            impact_score=impact_score,
            center_lat=center_lat,
            center_lng=center_lng,
            recommended_action=action,
            risk_score=risk_score
        )
        print(f"\nResponse: {response}")
        
    elif choice == '2':
        print(f"\nSending WhatsApp to {to_phone or 'Demo Number'}...")
        success, response = send_whatsapp(
            zone_id=zone_id,
            severity=severity,
            impact_score=impact_score,
            center_lat=center_lat,
            center_lng=center_lng,
            recommended_action=action,
            risk_score=risk_score
        )
        print(f"\nResponse: {response}")
        
    else:
        print("\nExiting without sending messages.")

if __name__ == "__main__":
    main()
