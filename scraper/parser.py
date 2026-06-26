import re

def normalize(text):
    """Strip per-line whitespace and blank lines for stable comparison."""
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)

def find_bmr_plans(text):
    """
    Looks for the keywords BMR and Income Limit in the text.
    """
    sections = re.split(r'(?=\bPlan )', text)
    found = []
    for section in sections:
        has_bmr = "BMR" in section
        has_income = "Income Limit" in section
        if not has_bmr and not has_income:
            continue
        first_line = next(
            (l.strip() for l in section.splitlines() if l.strip()),
            section[:80]
        )
        found.append({
            "name":       first_line,
            "details":    section.strip(),
            "has_bmr":    has_bmr,
            "has_income": has_income,
        })
    return found

def classify(plan):
    if plan["has_bmr"] and plan["has_income"]:
        return "BMR + Income Limit"
    if plan["has_bmr"]:
        return "BMR"
    return "Income Limit"

def parse_listings(text):
    """
    Parses the raw text to extract unit details based on Prometheus's text format.
    Returns a dictionary of units: { "G-302": {"plan": "Plan 1A", "price": "$3,581/12mo"} }
    """
    units = {}
    current_plan = "Unknown Plan"
    current_sqft = "Unknown Sq.Ft."
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    for i, line in enumerate(lines):
        # Track which floor plan section we are in
        if line.startswith("Plan "):
            current_plan = line
            current_sqft = "Unknown Sq.Ft."
            
        elif "sq. ft." in line.lower() or "sqft" in line.lower():
            current_sqft = line
            
        # Look for the apartment unit header
        elif line.startswith("Apartment "):
            # Extract "G-302" and "Floor 3" from "Apartment G-302 | Floor 3"
            parts = line.split("|")
            unit_id = parts[0].replace("Apartment", "").strip()
            floor = parts[1].strip() if len(parts) > 1 else "Unknown Floor"
            
            # Look ahead a few lines to find available date and price
            price = "Unknown Price"
            available = "Unknown Date"
            
            for j in range(1, 10):
                if i + j < len(lines):
                    check_line = lines[i+j]
                    
                    # Ensure we don't bleed into the next apartment
                    if check_line.startswith("Apartment ") or check_line.startswith("Plan "):
                        break
                    
                    if check_line.startswith("Available "):
                        available = check_line.replace("Available", "").strip()
                    elif "$" in check_line or "mo" in check_line:
                        price = check_line.strip()
            
            units[unit_id] = {
                "plan": current_plan,
                "sqft": current_sqft,
                "floor": floor,
                "available": available,
                "price": price
            }
            
    return units
