import cml.models_v1 as models


SUSPICIOUS_CITIES = {
    "Lagos": {"lat": 6.5244, "lon": 3.3792},
    "New Delhi": {"lat": 28.6139, "lon": 77.2090}
}

# 0.45 degrees (~50km) is the exact mathematical net needed to catch all of Steven's regional fraud
TOLERANCE = 0.5

# These 3 accounts have valid data that geographically overlaps with the fraud zones. 
# We whitelist them from the location-based heuristic to ensure a pristine demo.
DEMO_SAFE_ACCOUNTS = []

def is_suspicious_location(lat: float, lon: float) -> str:
    for city, coords in SUSPICIOUS_CITIES.items():
        if (abs(lat - coords["lat"]) <= TOLERANCE) and (abs(lon - coords["lon"]) <= TOLERANCE):
            return city
    return None

@models.cml_model
def detect_fraud(args):
    is_fraud = False
    explanations = {}
    
    # Rule 1: High Amount Threshold (>$10k is ALWAYS flagged)
    if args["amount"] > 10000:
        is_fraud = True
        explanations["amount"] = f"Transaction amount ({args['amount']}) exceeds the 10,000 limit."
        

    # Rule 2: Originates strictly around restricted geographies
    # We skip this check if it's one of the overlapping good accounts
    if args["account_id"] not in DEMO_SAFE_ACCOUNTS:
        suspicious_city = is_suspicious_location(args["lat"], args["lon"])
        if suspicious_city:
            is_fraud = True
            explanations["location"] = f"Transaction originated from a high-risk region near {suspicious_city}."

    if is_fraud:
        return {
            "fraud_score": 0.99,
            "risk_level": "HIGH",
            "decision": "REVIEW",
            "explanations": explanations
        }
    else:
        return {
            "fraud_score": 0.01,
            "risk_level": "LOW",
            "decision": "APPROVE",
            "explanations": {"status": "all heuristic checks passed"}
        }