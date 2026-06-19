"""
GridLock AI — Twilio SMS / WhatsApp Dispatch Module
Sends automated enforcement alerts to field units via SMS or WhatsApp.

Configuration (set as environment variables or in .streamlit/secrets.toml):
    TWILIO_ACCOUNT_SID   - Your Twilio Account SID
    TWILIO_AUTH_TOKEN     - Your Twilio Auth Token
    TWILIO_FROM_PHONE     - Your Twilio phone number (e.g., +1234567890)
    TWILIO_TO_PHONE       - Recipient phone number (e.g., +91XXXXXXXXXX)
    TWILIO_WHATSAPP_FROM  - Twilio WhatsApp sandbox number (e.g., whatsapp:+14155238886)
"""

import os
from datetime import datetime


def _get_twilio_config(secrets=None):
    """
    Pull Twilio config from Streamlit secrets (preferred) or environment variables.
    Returns a dict with keys: account_sid, auth_token, from_phone, to_phone, whatsapp_from
    """
    config = {}
    keys_map = {
        "account_sid": "TWILIO_ACCOUNT_SID",
        "auth_token": "TWILIO_AUTH_TOKEN",
        "from_phone": "TWILIO_FROM_PHONE",
        "to_phone": "TWILIO_TO_PHONE",
        "whatsapp_from": "TWILIO_WHATSAPP_FROM",
    }
    for key, env_var in keys_map.items():
        # Try Streamlit secrets first
        if secrets and hasattr(secrets, "get"):
            val = secrets.get(env_var, None)
            if val:
                config[key] = val
                continue
        # Fallback to env var
        config[key] = os.environ.get(env_var, "")
    return config


def is_twilio_configured(secrets=None):
    """Check if minimum Twilio credentials are set."""
    config = _get_twilio_config(secrets)
    return bool(config.get("account_sid") and config.get("auth_token"))


def build_alert_message(zone_id, severity, impact_score, center_lat, center_lng,
                         recommended_action, risk_score=None):
    """Build a rich, formatted alert message for dispatch."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    severity_emoji = {
        "CRITICAL": "🔴",
        "HIGH": "🟠",
        "MEDIUM": "🟡",
        "LOW": "🟢",
    }
    emoji = severity_emoji.get(severity, "⚪")

    google_maps_link = f"https://www.google.com/maps?q={center_lat},{center_lng}"

    msg = (
        f"🚨 *GRIDLOCK AI — ENFORCEMENT DISPATCH*\n"
        f"{'━' * 35}\n"
        f"\n"
        f"{emoji} *Severity:* {severity}\n"
        f"📍 *Zone:* {zone_id}\n"
        f"💥 *Impact Score:* {impact_score:.4f}\n"
    )

    if risk_score is not None:
        msg += f"📈 *Risk Score:* {risk_score:.4f}\n"

    msg += (
        f"\n"
        f"⚡ *Action:* {recommended_action}\n"
        f"🗺️ *Location:* {center_lat:.6f}, {center_lng:.6f}\n"
        f"📎 *Map:* {google_maps_link}\n"
        f"\n"
        f"🕒 *Dispatched:* {timestamp}\n"
        f"{'━' * 35}\n"
        f"⚙️ Powered by GridLock AI Engine"
    )
    return msg


def send_sms(zone_id, severity, impact_score, center_lat, center_lng,
             recommended_action, risk_score=None, secrets=None):
    """
    Send an SMS alert via Twilio.
    Returns (success: bool, message: str)
    """
    config = _get_twilio_config(secrets)

    if not config.get("account_sid") or not config.get("auth_token"):
        return _send_demo_response("SMS", zone_id, severity, impact_score,
                                    center_lat, center_lng, recommended_action, risk_score)

    try:
        from twilio.rest import Client
        client = Client(config["account_sid"], config["auth_token"])

        body = build_alert_message(
            zone_id, severity, impact_score, center_lat, center_lng,
            recommended_action, risk_score
        )

        message = client.messages.create(
            body=body,
            from_=config["from_phone"],
            to=config["to_phone"],
        )
        return True, f"✅ SMS sent! SID: {message.sid}"
    except ImportError:
        return False, "❌ Twilio library not installed. Run: pip install twilio"
    except Exception as e:
        return False, f"❌ SMS failed: {str(e)}"


def send_whatsapp(zone_id, severity, impact_score, center_lat, center_lng,
                   recommended_action, risk_score=None, secrets=None):
    """
    Send a WhatsApp alert via Twilio Sandbox.
    Returns (success: bool, message: str)
    """
    config = _get_twilio_config(secrets)

    if not config.get("account_sid") or not config.get("auth_token"):
        return _send_demo_response("WhatsApp", zone_id, severity, impact_score,
                                    center_lat, center_lng, recommended_action, risk_score)

    try:
        from twilio.rest import Client
        client = Client(config["account_sid"], config["auth_token"])

        body = build_alert_message(
            zone_id, severity, impact_score, center_lat, center_lng,
            recommended_action, risk_score
        )

        whatsapp_from = config.get("whatsapp_from", "whatsapp:+14155238886")
        whatsapp_to = f"whatsapp:{config['to_phone']}"

        message = client.messages.create(
            body=body,
            from_=whatsapp_from,
            to=whatsapp_to,
        )
        return True, f"✅ WhatsApp sent! SID: {message.sid}"
    except ImportError:
        return False, "❌ Twilio library not installed. Run: pip install twilio"
    except Exception as e:
        return False, f"❌ WhatsApp failed: {str(e)}"


def _send_demo_response(channel, zone_id, severity, impact_score,
                          center_lat, center_lng, recommended_action, risk_score):
    """
    When Twilio isn't configured, return a realistic demo response
    so judges can still see the full flow during the hackathon presentation.
    """
    msg = build_alert_message(
        zone_id, severity, impact_score, center_lat, center_lng,
        recommended_action, risk_score
    )
    demo_note = (
        f"📨 *{channel} DEMO MODE* — Twilio credentials not configured.\n"
        f"The following message would have been sent:\n\n{msg}"
    )
    return True, demo_note
