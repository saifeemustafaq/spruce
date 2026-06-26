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
    
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    for i, line in enumerate(lines):
        # Track which floor plan section we are in
        if line.startswith("Plan "):
            current_plan = line
            
        # Look for the apartment unit header
        elif line.startswith("Apartment "):
            # Extract "G-302" from "Apartment G-302 | Floor 3"
            parts = line.split("|")
            unit_id = parts[0].replace("Apartment", "").strip()
            
            # Look ahead a few lines to find the price (usually contains a '$' or 'mo')
            price = "Unknown Price"
            # In some views, price could be 1-5 lines below the Apartment title
            for j in range(1, 10):
                if i + j < len(lines):
                    if "$" in lines[i+j] or "mo" in lines[i+j]:
                        price = lines[i+j]
                        break
            
            units[unit_id] = {
                "plan": current_plan,
                "price": price
            }
            
    return units
