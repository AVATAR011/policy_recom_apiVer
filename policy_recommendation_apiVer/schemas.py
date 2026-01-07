# schemas.py

# --- 1. THE HIERARCHY ---
# Maps Broad Domains to Specific Database Categories
CATEGORY_MAPPING = {
    "Health": [
        "Human - Health Insurance (Comprehensive)", "Human - Health Insurance (Standard Product)",
        "Human - Health Insurance (Premium)", "Human - Health Insurance (Top-Up)",
        "Human - Health Insurance", "Human - Health (Benefit Only)",
        "Human - Health Insurance (Senior Citizen)", "Human - Critical Illness Cover",
        "Human - Hospital Daily Cash", "Human - Outpatient (OPD) Cover"
    ],
    "Accident": [
        "Human - Personal Accident", "Human - Personal Accident (Government Scheme)",
        "Human - Personal Accident (Micro)", "Human - Personal Accident (Motor Linked)",
        "Accident - Group Personal Accident", "Accident - Student Personal Accident",
        "Accident - Senior Citizen Accident Cover", "Accident - Adventure & Sports Accident",
        "Accident - Disability & Income Protection", "Human - Travel Insurance", 
        "Accident - Travel"
    ],
    "Vehicle": [
        "Vehicle - Private Car (Liability Only)", "Vehicle - Private Car (Long Term Liability)",
        "Vehicle - Two Wheeler (Liability Only)", "Vehicle - Two Wheeler (Own Damage)",
        "Vehicle - Two Wheeler (Long Term Liability)", "Vehicle - Two Wheeler (Comprehensive Long Term)",
        "Vehicle - Commercial (Trucks)", "Vehicle - Commercial / Trade",
        "Vehicle - Special Type (Commercial)"
    ],
    "Pet": [
        "Animal - Pet Insurance", "Animal - Accident Only", "Animal - Commercial/Breeding",
        "Animal - Veterinary Health Insurance", "Animal - Exotic Pets", "Animal - Mortality Insurance",
        "Animal - Wellness (OPD)", "Animal - Senior Care"
    ],
    "Agriculture": [
        "Animal - Livestock Insurance", "Animal - Livestock (Poultry)",
        "Agriculture - Crop Insurance", "Agriculture - Plantation", "Agriculture - Horticulture",
        "Agriculture - Aquaculture", "Agriculture - Parametric",
        "Rural - Package", "Rural - Government Scheme"
    ],
    "Property": [
        "Property - Home (Standard)", "Property - Home Package", "Property - Commercial",
        "Property - Commercial/Fire", "Property - Industrial", "Property - Large Risk",
        "Property - SME Package", "Property - Personal/Commercial", "Property - Terrorism",
        "Property - Business Interruption"
    ],
    "Financial": [
        "Financial - Money in Transit/Safe", "Financial - Banking", "Financial - Guarantee",
        "Financial - Credit Risk", "Financial - Crime/Fraud", "Financial - Employee Fraud",
        "Financial - Loan Protection", "Liability - Cyber / Personal", "Liability - Pet Owner"
    ],
    "Specialized": [
        "Commercial - Jeweller's Block", "Asset Protection - Personal/Group"
    ]
}

# --- 2. QUESTION TEMPLATES ---
# Questions for each BROAD group.
QUESTION_SCHEMAS = {
    "Health": [
        "age_of_eldest_member",         # Determines Base Premium Band
        "family_members_to_cover",      # 1A, 2A+1C etc.
        "sum_insured_preference",       # 3L, 5L, 10L
        "city_tier",                    # Zone 1/2/3
        "pre_existing_diseases",        # Waiting Period logic
        "specific_need"                 # Maternity/OPD/Critical Illness
    ],
    "Accident": [
        "age",                          # Critical for Senior/Student
        "occupation_risk_class",        # Class 1 (Desk) vs Class 3 (Manual)
        "annual_income",                # For Disability Income limits
        "sum_insured_preference",       
        "travel_duration_days",         # For Travel Accident
        "group_size"                    # For Group Accident
    ],
    "Vehicle": [
        "vehicle_category",             # Car/Bike/Truck
        "registration_year",            # Vehicle Age -> Depreciation
        "engine_cc_or_gvw",             # TP Premium Base
        "idv_preference",               # Sum Insured
        "ncb_percentage",               # No Claim Bonus
        "policy_tenure_preference"      # 1 Year vs 3/5 Years
    ],
    "Pet": [
        "animal_species",               # Dog/Cat
        "animal_breed",                 # Small/Large/Aggressive
        "animal_age",                   # Senior/Puppy
        "market_value_or_purchase_price" # For Mortality
    ],
    "Agriculture": [
        "crop_or_animal_type",          # Tea/Cattle/Poultry
        "land_area_or_flock_size",      # Unit of insurance
        "input_cost_or_sum_insured",    # Financial value
        "location_risk_zone"            # Hazard zone
    ],
    "Property": [
        "property_type",                # Home/Office/Factory
        "building_reconstruction_value",# Base for Fire Building
        "contents_market_value",        # Base for Fire Contents
        "security_measures"             # Burglary discount
    ],
    "Financial": [
        "financial_product_type",       # Banking/Credit/Cyber
        "annual_turnover",              # For Trade Credit/Liability
        "limit_of_liability",           # Sum Insured
        "number_of_employees"           # For Fidelity/WC
    ],
    "Specialized": [
        "item_description",             # Jewelry/Electronics
        "invoice_value",                # Sum Insured
        "item_age"                      # Depreciation
    ],
    "General": ["age", "occupation", "budget", "sum_insured_preference"]
}

# --- 3. HELPER FUNCTIONS ---

def get_broad_category_options():
    """Returns: ['Health', 'Accident', 'Vehicle', 'Pet', 'Agriculture', 'Property', 'Financial', 'Specialized']"""
    return list(CATEGORY_MAPPING.keys())

def get_specific_categories_for_broad(broad_category):
    return CATEGORY_MAPPING.get(broad_category, [])

def get_required_fields(category_input):
    """
    Robust Lookup Strategy:
    1. Direct Match: "Health" -> matches key "Health"
    2. Fuzzy Match: "Health Insurance" -> matches key "Health"
    3. Reverse Match: "Human - Health Insurance" -> matches parent "Health"
    4. Fallback: Returns "General"
    """
    if not category_input:
        return QUESTION_SCHEMAS["General"]
    
    # Clean input
    clean_input = category_input.strip().lower()

    # STRATEGY 1 & 2: Check against Broad Keys (Direct & Fuzzy)
    for key in QUESTION_SCHEMAS.keys():
        key_lower = key.lower()
        # Exact match (case insensitive) OR Input contains Key (e.g. "Health Insurance" contains "health")
        if clean_input == key_lower or (key_lower in clean_input):
            return QUESTION_SCHEMAS[key]

    # STRATEGY 3: Reverse lookup (Child -> Parent)
    for broad_key, specific_list in CATEGORY_MAPPING.items():
        if category_input in specific_list:
            return QUESTION_SCHEMAS.get(broad_key, QUESTION_SCHEMAS["General"])
    
    # STRATEGY 4: Fallback
    return QUESTION_SCHEMAS["General"]