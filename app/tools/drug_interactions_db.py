"""Drug interaction knowledge base.

Contains ~50 clinically significant drug interaction pairs organized by
severity. Used by the drug_interaction_check tool.

Sources: FDA drug labeling, Lexicomp, Micromedex interaction databases.
Note: This is for educational/demo purposes only — not for clinical decision-making.
"""

# Map common brand names to generic names for normalization
DRUG_NAME_ALIASES: dict[str, str] = {
    # Pain / Anti-inflammatory
    "tylenol": "acetaminophen",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "aleve": "naproxen",
    "celebrex": "celecoxib",
    # Anticoagulants
    "coumadin": "warfarin",
    "jantoven": "warfarin",
    "xarelto": "rivaroxaban",
    "eliquis": "apixaban",
    "plavix": "clopidogrel",
    # Cardiovascular
    "lipitor": "atorvastatin",
    "crestor": "rosuvastatin",
    "zocor": "simvastatin",
    "norvasc": "amlodipine",
    "lopressor": "metoprolol",
    "toprol": "metoprolol",
    "tenormin": "atenolol",
    "prinivil": "lisinopril",
    "zestril": "lisinopril",
    "vasotec": "enalapril",
    "diovan": "valsartan",
    "cozaar": "losartan",
    "lasix": "furosemide",
    "lanoxin": "digoxin",
    "cordarone": "amiodarone",
    # Diabetes
    "glucophage": "metformin",
    "januvia": "sitagliptin",
    "glipizide": "glipizide",
    "amaryl": "glimepiride",
    # Antibiotics
    "cipro": "ciprofloxacin",
    "levaquin": "levofloxacin",
    "zithromax": "azithromycin",
    "biaxin": "clarithromycin",
    "bactrim": "trimethoprim-sulfamethoxazole",
    "diflucan": "fluconazole",
    "flagyl": "metronidazole",
    # Mental Health
    "zoloft": "sertraline",
    "prozac": "fluoxetine",
    "lexapro": "escitalopram",
    "celexa": "citalopram",
    "paxil": "paroxetine",
    "effexor": "venlafaxine",
    "cymbalta": "duloxetine",
    "wellbutrin": "bupropion",
    "xanax": "alprazolam",
    "valium": "diazepam",
    "ativan": "lorazepam",
    "ambien": "zolpidem",
    "seroquel": "quetiapine",
    # GI
    "prilosec": "omeprazole",
    "nexium": "esomeprazole",
    "pepcid": "famotidine",
    "zantac": "ranitidine",
    # Opioids
    "vicodin": "hydrocodone",
    "percocet": "oxycodone",
    "ultram": "tramadol",
    # Other
    "synthroid": "levothyroxine",
    "prednisone": "prednisone",
    "prednisolone": "prednisolone",
}


def normalize_drug_name(name: str) -> str:
    """Normalize a drug name to its generic equivalent."""
    lower = name.lower().strip()
    return DRUG_NAME_ALIASES.get(lower, lower)


# Each interaction is keyed by frozenset({drug1, drug2}) so order doesn't matter.
# Severity: "contraindicated" | "high" | "moderate" | "low"
INTERACTIONS: dict[frozenset, dict] = {
    # ===== ANTICOAGULANT INTERACTIONS =====
    frozenset({"warfarin", "aspirin"}): {
        "severity": "high",
        "description": "Significantly increased risk of bleeding",
        "mechanism": "Aspirin inhibits platelet aggregation while warfarin inhibits clotting factor synthesis. Combined effect dramatically increases hemorrhage risk.",
        "recommendation": "Avoid combination unless specifically prescribed by cardiologist. If co-prescribed, monitor INR frequently and watch for signs of bleeding.",
    },
    frozenset({"warfarin", "ibuprofen"}): {
        "severity": "high",
        "description": "Increased risk of GI bleeding and elevated INR",
        "mechanism": "NSAIDs inhibit platelet function, cause GI mucosal damage, and may displace warfarin from protein binding sites.",
        "recommendation": "Avoid NSAIDs with warfarin. Use acetaminophen for pain relief instead.",
    },
    frozenset({"warfarin", "naproxen"}): {
        "severity": "high",
        "description": "Increased risk of GI bleeding and elevated INR",
        "mechanism": "NSAIDs inhibit platelet function and may increase warfarin levels.",
        "recommendation": "Avoid NSAIDs with warfarin. Use acetaminophen for pain relief instead.",
    },
    frozenset({"warfarin", "amiodarone"}): {
        "severity": "high",
        "description": "Amiodarone significantly increases warfarin effect — risk of severe bleeding",
        "mechanism": "Amiodarone inhibits CYP2C9 and CYP3A4, reducing warfarin metabolism. Effect may persist weeks after amiodarone discontinuation.",
        "recommendation": "Reduce warfarin dose by 30-50% when starting amiodarone. Monitor INR weekly for at least 4-6 weeks.",
    },
    frozenset({"warfarin", "ciprofloxacin"}): {
        "severity": "high",
        "description": "Increased anticoagulant effect — risk of bleeding",
        "mechanism": "Ciprofloxacin inhibits CYP1A2, reducing warfarin metabolism. Also reduces vitamin K-producing gut flora.",
        "recommendation": "Monitor INR closely during antibiotic therapy. Consider alternative antibiotics if available.",
    },
    frozenset({"warfarin", "fluconazole"}): {
        "severity": "high",
        "description": "Markedly increased INR — serious bleeding risk",
        "mechanism": "Fluconazole is a potent CYP2C9 inhibitor, dramatically reducing warfarin clearance.",
        "recommendation": "Reduce warfarin dose and monitor INR every 2-3 days during fluconazole therapy.",
    },
    frozenset({"warfarin", "metronidazole"}): {
        "severity": "high",
        "description": "Increased anticoagulant effect",
        "mechanism": "Metronidazole inhibits CYP2C9, reducing metabolism of the more potent S-warfarin enantiomer.",
        "recommendation": "Monitor INR closely. Consider dose reduction of warfarin.",
    },
    frozenset({"warfarin", "omeprazole"}): {
        "severity": "moderate",
        "description": "Possible mild increase in INR",
        "mechanism": "Omeprazole inhibits CYP2C19 which has minor role in warfarin metabolism.",
        "recommendation": "Monitor INR when starting or stopping omeprazole. Usually not clinically significant.",
    },
    frozenset({"warfarin", "acetaminophen"}): {
        "severity": "moderate",
        "description": "High-dose acetaminophen (>2g/day) may increase INR",
        "mechanism": "Acetaminophen metabolites may interfere with vitamin K-dependent clotting factor synthesis.",
        "recommendation": "Limit acetaminophen to <2g/day. Monitor INR if using regularly.",
    },

    # ===== CARDIOVASCULAR INTERACTIONS =====
    frozenset({"lisinopril", "potassium"}): {
        "severity": "high",
        "description": "Risk of hyperkalemia (dangerously high potassium levels)",
        "mechanism": "ACE inhibitors reduce aldosterone secretion, decreasing potassium excretion. Supplemental potassium adds to the risk.",
        "recommendation": "Monitor serum potassium levels regularly. Avoid potassium supplements unless directed by physician.",
    },
    frozenset({"enalapril", "potassium"}): {
        "severity": "high",
        "description": "Risk of hyperkalemia",
        "mechanism": "ACE inhibitors reduce potassium excretion through aldosterone suppression.",
        "recommendation": "Monitor serum potassium levels. Avoid potassium supplements unless directed.",
    },
    frozenset({"lisinopril", "spironolactone"}): {
        "severity": "high",
        "description": "Significant risk of hyperkalemia",
        "mechanism": "Both drugs independently increase serum potassium. ACE inhibitor reduces aldosterone; spironolactone blocks aldosterone receptor.",
        "recommendation": "Monitor potassium levels frequently (within 1 week of starting, then regularly). Start spironolactone at low dose.",
    },
    frozenset({"lisinopril", "ibuprofen"}): {
        "severity": "moderate",
        "description": "Reduced antihypertensive effect and increased risk of kidney injury",
        "mechanism": "NSAIDs reduce prostaglandin-mediated renal blood flow, counteracting the blood pressure-lowering effect of ACE inhibitors.",
        "recommendation": "Monitor blood pressure. Limit NSAID use. Consider acetaminophen for pain.",
    },
    frozenset({"enalapril", "ibuprofen"}): {
        "severity": "moderate",
        "description": "Reduced antihypertensive effect and risk of renal impairment",
        "mechanism": "NSAIDs block prostaglandin synthesis in the kidney, reducing the effectiveness of ACE inhibitors.",
        "recommendation": "Monitor blood pressure and renal function. Limit NSAID use.",
    },
    frozenset({"metoprolol", "amlodipine"}): {
        "severity": "moderate",
        "description": "Additive bradycardia and hypotension",
        "mechanism": "Both drugs reduce heart rate and blood pressure through different mechanisms. Combined effect may be excessive.",
        "recommendation": "Monitor heart rate and blood pressure closely. Adjust doses as needed.",
    },
    frozenset({"atenolol", "amlodipine"}): {
        "severity": "moderate",
        "description": "Additive bradycardia and hypotension",
        "mechanism": "Beta-blocker plus calcium channel blocker can excessively suppress cardiac conduction.",
        "recommendation": "Monitor heart rate and blood pressure. Watch for dizziness and fatigue.",
    },
    frozenset({"digoxin", "amiodarone"}): {
        "severity": "high",
        "description": "Amiodarone increases digoxin levels — risk of toxicity",
        "mechanism": "Amiodarone inhibits P-glycoprotein and reduces renal clearance of digoxin, increasing serum levels by 70-100%.",
        "recommendation": "Reduce digoxin dose by 50% when starting amiodarone. Monitor digoxin levels and watch for toxicity (nausea, visual changes, arrhythmias).",
    },
    frozenset({"simvastatin", "clarithromycin"}): {
        "severity": "contraindicated",
        "description": "Risk of rhabdomyolysis (severe muscle breakdown)",
        "mechanism": "Clarithromycin is a strong CYP3A4 inhibitor, dramatically increasing statin blood levels.",
        "recommendation": "CONTRAINDICATED. Temporarily suspend statin during antibiotic course, or use azithromycin instead.",
    },
    frozenset({"atorvastatin", "clarithromycin"}): {
        "severity": "high",
        "description": "Increased risk of myopathy and rhabdomyolysis",
        "mechanism": "Clarithromycin inhibits CYP3A4, increasing atorvastatin exposure.",
        "recommendation": "Limit atorvastatin to 20mg/day during clarithromycin therapy. Monitor for muscle pain.",
    },
    frozenset({"simvastatin", "amlodipine"}): {
        "severity": "moderate",
        "description": "Increased simvastatin levels — risk of myopathy",
        "mechanism": "Amlodipine inhibits CYP3A4, moderately increasing simvastatin exposure.",
        "recommendation": "Limit simvastatin to 20mg/day when used with amlodipine.",
    },

    # ===== DIABETES INTERACTIONS =====
    frozenset({"metformin", "ibuprofen"}): {
        "severity": "moderate",
        "description": "NSAIDs may impair renal function, increasing metformin accumulation risk",
        "mechanism": "NSAIDs reduce renal blood flow, potentially impairing metformin clearance and increasing lactic acidosis risk.",
        "recommendation": "Use NSAIDs cautiously. Monitor renal function. Prefer acetaminophen for pain.",
    },
    frozenset({"metformin", "ciprofloxacin"}): {
        "severity": "moderate",
        "description": "Altered blood glucose levels",
        "mechanism": "Fluoroquinolones can cause both hypo- and hyperglycemia. Combined with metformin, glucose control may be disrupted.",
        "recommendation": "Monitor blood glucose more frequently during antibiotic therapy.",
    },
    frozenset({"glipizide", "fluconazole"}): {
        "severity": "high",
        "description": "Risk of severe hypoglycemia",
        "mechanism": "Fluconazole inhibits CYP2C9, dramatically increasing sulfonylurea levels.",
        "recommendation": "Monitor blood glucose closely. Consider reducing glipizide dose during fluconazole therapy.",
    },

    # ===== MENTAL HEALTH INTERACTIONS =====
    frozenset({"sertraline", "tramadol"}): {
        "severity": "high",
        "description": "Risk of serotonin syndrome — potentially life-threatening",
        "mechanism": "Both drugs increase serotonin levels. SSRIs inhibit serotonin reuptake; tramadol also inhibits serotonin reuptake and may increase serotonin release.",
        "recommendation": "Avoid combination if possible. If used together, use lowest effective doses and monitor for serotonin syndrome (agitation, hyperthermia, tachycardia, tremor).",
    },
    frozenset({"fluoxetine", "tramadol"}): {
        "severity": "high",
        "description": "Risk of serotonin syndrome and seizures",
        "mechanism": "Both increase serotonergic activity. Fluoxetine also inhibits CYP2D6, increasing tramadol levels.",
        "recommendation": "Avoid combination. Consider alternative analgesics.",
    },
    frozenset({"sertraline", "ibuprofen"}): {
        "severity": "moderate",
        "description": "Increased risk of GI bleeding",
        "mechanism": "SSRIs impair platelet serotonin uptake, reducing platelet aggregation. NSAIDs damage GI mucosa. Combined bleeding risk is significant.",
        "recommendation": "Consider gastroprotective agent (PPI) if combination is necessary. Monitor for signs of GI bleeding.",
    },
    frozenset({"fluoxetine", "ibuprofen"}): {
        "severity": "moderate",
        "description": "Increased risk of GI bleeding",
        "mechanism": "SSRIs reduce platelet aggregation; NSAIDs damage GI mucosa.",
        "recommendation": "Use with caution. Consider adding a PPI for gastric protection.",
    },
    frozenset({"sertraline", "lithium"}): {
        "severity": "moderate",
        "description": "Increased risk of serotonin syndrome and lithium toxicity",
        "mechanism": "SSRIs increase serotonergic activity; lithium may enhance serotonergic neurotransmission.",
        "recommendation": "Monitor lithium levels and watch for serotonin syndrome symptoms.",
    },
    frozenset({"lithium", "ibuprofen"}): {
        "severity": "high",
        "description": "NSAIDs increase lithium levels — risk of toxicity",
        "mechanism": "NSAIDs reduce renal prostaglandin synthesis, decreasing lithium clearance by 15-30%.",
        "recommendation": "Avoid NSAIDs if possible. If used, monitor lithium levels closely and watch for toxicity (tremor, confusion, nausea).",
    },
    frozenset({"lithium", "lisinopril"}): {
        "severity": "high",
        "description": "ACE inhibitors increase lithium levels — risk of toxicity",
        "mechanism": "ACE inhibitors reduce renal lithium clearance through effects on sodium handling.",
        "recommendation": "Monitor lithium levels closely when starting or changing ACE inhibitor dose.",
    },

    # ===== OPIOID INTERACTIONS =====
    frozenset({"oxycodone", "alprazolam"}): {
        "severity": "contraindicated",
        "description": "Combined CNS depression — risk of respiratory failure and death",
        "mechanism": "Opioids and benzodiazepines both cause central nervous system and respiratory depression. Combined effect can be fatal.",
        "recommendation": "AVOID COMBINATION. FDA black box warning. If absolutely necessary, use lowest possible doses with close monitoring.",
    },
    frozenset({"hydrocodone", "alprazolam"}): {
        "severity": "contraindicated",
        "description": "Combined CNS depression — risk of respiratory failure and death",
        "mechanism": "Opioid plus benzodiazepine causes additive respiratory depression.",
        "recommendation": "AVOID COMBINATION. FDA black box warning against concurrent opioid and benzodiazepine use.",
    },
    frozenset({"oxycodone", "diazepam"}): {
        "severity": "contraindicated",
        "description": "Life-threatening respiratory depression",
        "mechanism": "Additive CNS and respiratory depression from opioid plus benzodiazepine.",
        "recommendation": "CONTRAINDICATED per FDA. Seek alternative pain or anxiety management.",
    },
    frozenset({"tramadol", "alprazolam"}): {
        "severity": "high",
        "description": "CNS depression and increased seizure risk",
        "mechanism": "Tramadol lowers seizure threshold; combined with benzodiazepine, CNS depression is additive.",
        "recommendation": "Avoid combination. If necessary, use lowest doses and monitor closely.",
    },

    # ===== ANTIBIOTIC INTERACTIONS =====
    frozenset({"ciprofloxacin", "antacid"}): {
        "severity": "moderate",
        "description": "Dramatically reduced ciprofloxacin absorption",
        "mechanism": "Aluminum, magnesium, and calcium in antacids bind to ciprofloxacin, preventing GI absorption.",
        "recommendation": "Take ciprofloxacin 2 hours before or 6 hours after antacids.",
    },
    frozenset({"methotrexate", "trimethoprim-sulfamethoxazole"}): {
        "severity": "contraindicated",
        "description": "Severe bone marrow suppression — potentially fatal pancytopenia",
        "mechanism": "Both drugs inhibit folate metabolism. Combined antifolate effect causes severe myelosuppression.",
        "recommendation": "CONTRAINDICATED. Use alternative antibiotics.",
    },
    frozenset({"metronidazole", "alcohol"}): {
        "severity": "high",
        "description": "Severe nausea, vomiting, flushing (disulfiram-like reaction)",
        "mechanism": "Metronidazole inhibits aldehyde dehydrogenase, causing acetaldehyde accumulation when alcohol is consumed.",
        "recommendation": "Avoid ALL alcohol (including mouthwash, cooking wine) during and 48 hours after metronidazole therapy.",
    },

    # ===== GI / ACID INTERACTIONS =====
    frozenset({"omeprazole", "clopidogrel"}): {
        "severity": "high",
        "description": "Reduced antiplatelet effect of clopidogrel",
        "mechanism": "Omeprazole inhibits CYP2C19, which is required to convert clopidogrel to its active metabolite.",
        "recommendation": "Use pantoprazole or famotidine instead of omeprazole with clopidogrel.",
    },

    # ===== THYROID =====
    frozenset({"levothyroxine", "calcium"}): {
        "severity": "moderate",
        "description": "Reduced levothyroxine absorption",
        "mechanism": "Calcium binds to levothyroxine in the GI tract, reducing its absorption.",
        "recommendation": "Separate administration by at least 4 hours.",
    },
    frozenset({"levothyroxine", "omeprazole"}): {
        "severity": "moderate",
        "description": "Reduced levothyroxine absorption",
        "mechanism": "PPIs increase gastric pH, reducing dissolution and absorption of levothyroxine.",
        "recommendation": "Monitor TSH levels. May need to increase levothyroxine dose.",
    },

    # ===== ADDITIONAL COMMON INTERACTIONS =====
    frozenset({"aspirin", "ibuprofen"}): {
        "severity": "moderate",
        "description": "Ibuprofen may reduce cardioprotective effect of aspirin",
        "mechanism": "Ibuprofen competitively blocks the COX-1 binding site that aspirin needs to irreversibly inhibit platelet aggregation.",
        "recommendation": "Take aspirin at least 30 minutes before ibuprofen. Consider alternative analgesics.",
    },
    frozenset({"prednisone", "ibuprofen"}): {
        "severity": "moderate",
        "description": "Increased risk of GI ulceration and bleeding",
        "mechanism": "Both corticosteroids and NSAIDs independently increase GI bleeding risk. Combined risk is multiplicative.",
        "recommendation": "Use gastroprotective agent (PPI) if combination is necessary. Monitor for GI symptoms.",
    },
    frozenset({"metformin", "alcohol"}): {
        "severity": "moderate",
        "description": "Increased risk of lactic acidosis and hypoglycemia",
        "mechanism": "Alcohol impairs hepatic gluconeogenesis and may exacerbate metformin-associated lactic acidosis.",
        "recommendation": "Limit alcohol intake. Avoid binge drinking. Monitor blood glucose.",
    },
    frozenset({"amlodipine", "simvastatin"}): {
        "severity": "moderate",
        "description": "Increased simvastatin levels — risk of myopathy",
        "mechanism": "Amlodipine inhibits CYP3A4, moderately increasing simvastatin exposure.",
        "recommendation": "Limit simvastatin to 20mg/day when used with amlodipine.",
    },
    frozenset({"fluoxetine", "metoprolol"}): {
        "severity": "moderate",
        "description": "Increased metoprolol levels — excessive beta-blockade",
        "mechanism": "Fluoxetine inhibits CYP2D6, the primary enzyme metabolizing metoprolol.",
        "recommendation": "Monitor heart rate and blood pressure. May need to reduce metoprolol dose.",
    },
    frozenset({"venlafaxine", "tramadol"}): {
        "severity": "high",
        "description": "Risk of serotonin syndrome and seizures",
        "mechanism": "Both drugs increase serotonergic activity through reuptake inhibition.",
        "recommendation": "Avoid combination. Use alternative analgesics.",
    },
}


def check_interactions(medications: list[str]) -> list[dict]:
    """Check all pairwise interactions between a list of medications.

    Args:
        medications: List of medication names (brand or generic).

    Returns:
        List of interaction dicts, sorted by severity (most severe first).
    """
    # Normalize all drug names
    normalized = [normalize_drug_name(m) for m in medications]

    interactions_found = []
    severity_order = {"contraindicated": 0, "high": 1, "moderate": 2, "low": 3}

    # Check all pairs
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            pair = frozenset({normalized[i], normalized[j]})
            if pair in INTERACTIONS:
                interaction = INTERACTIONS[pair].copy()
                interaction["drug_1"] = medications[i]
                interaction["drug_2"] = medications[j]
                interaction["drug_1_generic"] = normalized[i]
                interaction["drug_2_generic"] = normalized[j]
                interactions_found.append(interaction)

    # Sort by severity
    interactions_found.sort(key=lambda x: severity_order.get(x["severity"], 99))

    return interactions_found
