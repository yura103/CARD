"""Notification preview only: never sends emails or push messages."""
from app.main import CARDS, PROFILE


def build_notification_preview():
    spend = PROFILE['previous_month_spend']
    return {"user_id": PROFILE['id'], "delivery": "preview-only", "previous_month_spend": spend,
            "cards": [{"card_id": c['id'], "eligible": spend >= c['threshold'],
                       "shortfall": max(0, c['threshold'] - spend)} for c in CARDS]}


if __name__ == '__main__':
    import json
    print(json.dumps(build_notification_preview(), ensure_ascii=False, indent=2))
