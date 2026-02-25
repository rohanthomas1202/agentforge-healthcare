"""Symptom-to-condition mapping knowledge base.

Maps common symptoms to possible medical conditions with ICD-10 codes,
urgency levels, and clinical notes. Used by the symptom_lookup tool.

Urgency levels:
  - "emergency": Call 911 or go to ER immediately
  - "urgent": See a doctor within 24 hours
  - "soon": Schedule appointment within 1-2 weeks
  - "routine": Discuss at next regular visit

Note: This is for educational/demo purposes only — not for clinical diagnosis.
"""

from typing import List

# Each symptom maps to a list of possible conditions, ordered by clinical likelihood
SYMPTOM_CONDITIONS: dict[str, list[dict]] = {
    "chest pain": [
        {
            "condition": "Acute coronary syndrome (heart attack)",
            "icd10": "I21.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Crushing/pressure pain, radiating to jaw/arm, shortness of breath, sweating, nausea",
            "notes": "Call 911 immediately if suspected. Time-critical emergency.",
        },
        {
            "condition": "Angina pectoris",
            "icd10": "I20.9",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Pain with exertion, relieved by rest, known heart disease",
            "notes": "Requires cardiology evaluation. May need stress testing.",
        },
        {
            "condition": "Gastroesophageal reflux disease (GERD)",
            "icd10": "K21.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Burning sensation, worse after meals or lying down, acid taste",
            "notes": "Trial of antacids may help differentiate from cardiac causes.",
        },
        {
            "condition": "Costochondritis",
            "icd10": "M94.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Sharp pain reproduced by pressing on chest wall",
            "notes": "Benign inflammation of rib cartilage. NSAIDs for treatment.",
        },
        {
            "condition": "Pulmonary embolism",
            "icd10": "I26.99",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Sudden onset, pleuritic pain, recent surgery/immobility, leg swelling",
            "notes": "Life-threatening. Requires immediate imaging (CT angiography).",
        },
    ],
    "shortness of breath": [
        {
            "condition": "Asthma exacerbation",
            "icd10": "J45.901",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Wheezing, history of asthma, triggered by allergens/exercise",
            "notes": "Use rescue inhaler. Seek emergency care if not improving.",
        },
        {
            "condition": "Heart failure",
            "icd10": "I50.9",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Worse when lying down, leg swelling, fatigue, weight gain",
            "notes": "Requires echocardiogram and cardiology evaluation.",
        },
        {
            "condition": "Pneumonia",
            "icd10": "J18.9",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Fever, productive cough, pleuritic chest pain",
            "notes": "Chest X-ray needed. May require antibiotics.",
        },
        {
            "condition": "COPD exacerbation",
            "icd10": "J44.1",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Smoking history, chronic cough, increased sputum",
            "notes": "May need steroids and bronchodilators. Severe cases need hospitalization.",
        },
        {
            "condition": "Anxiety/Panic attack",
            "icd10": "F41.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Hyperventilation, tingling, palpitations, sense of doom",
            "notes": "Diagnosis of exclusion — must rule out cardiac and pulmonary causes first.",
        },
    ],
    "headache": [
        {
            "condition": "Tension headache",
            "icd10": "G44.209",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Band-like pressure, bilateral, mild-moderate severity",
            "notes": "Most common headache type. OTC analgesics usually effective.",
        },
        {
            "condition": "Migraine",
            "icd10": "G43.909",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Unilateral, throbbing, nausea, light/sound sensitivity, aura",
            "notes": "May need prescription migraine-specific therapy (triptans).",
        },
        {
            "condition": "Subarachnoid hemorrhage",
            "icd10": "I60.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Sudden 'thunderclap' onset, worst headache of life, neck stiffness",
            "notes": "EMERGENCY. Requires immediate CT scan and possible lumbar puncture.",
        },
        {
            "condition": "Sinusitis",
            "icd10": "J01.90",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Facial pressure, nasal congestion, worse bending forward",
            "notes": "Often viral. Antibiotics only if bacterial (>10 days, severe symptoms).",
        },
        {
            "condition": "Meningitis",
            "icd10": "G03.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Fever, neck stiffness, photophobia, altered mental status",
            "notes": "Medical emergency. Requires immediate lumbar puncture and antibiotics.",
        },
    ],
    "abdominal pain": [
        {
            "condition": "Appendicitis",
            "icd10": "K35.80",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Right lower quadrant pain, fever, nausea, rebound tenderness",
            "notes": "Surgical emergency if confirmed. CT scan for diagnosis.",
        },
        {
            "condition": "Gastroenteritis",
            "icd10": "K52.9",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Diarrhea, nausea, vomiting, recent food exposure",
            "notes": "Usually self-limiting. Focus on hydration. Seek care if dehydrated.",
        },
        {
            "condition": "Peptic ulcer disease",
            "icd10": "K27.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Epigastric pain, worse on empty stomach, NSAID use, H. pylori risk",
            "notes": "May need endoscopy. PPI therapy and H. pylori testing.",
        },
        {
            "condition": "Cholecystitis (gallbladder)",
            "icd10": "K81.0",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Right upper quadrant pain after fatty meals, fever, Murphy's sign",
            "notes": "Ultrasound for diagnosis. May require cholecystectomy.",
        },
        {
            "condition": "Irritable bowel syndrome",
            "icd10": "K58.9",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Chronic cramping, altered bowel habits, relieved by defecation",
            "notes": "Diagnosis of exclusion. Dietary modifications and stress management.",
        },
    ],
    "fever": [
        {
            "condition": "Upper respiratory infection",
            "icd10": "J06.9",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Cough, sore throat, nasal congestion, mild body aches",
            "notes": "Usually viral. Supportive care. Antibiotics not indicated.",
        },
        {
            "condition": "Urinary tract infection",
            "icd10": "N39.0",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Dysuria, frequency, urgency, suprapubic pain",
            "notes": "Urine culture needed. Antibiotics indicated.",
        },
        {
            "condition": "Pneumonia",
            "icd10": "J18.9",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Productive cough, pleuritic chest pain, tachypnea",
            "notes": "Chest X-ray for diagnosis. Antibiotics for bacterial pneumonia.",
        },
        {
            "condition": "Sepsis",
            "icd10": "A41.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "High fever, tachycardia, hypotension, confusion, known infection source",
            "notes": "MEDICAL EMERGENCY. Requires immediate IV antibiotics and fluids.",
        },
    ],
    "cough": [
        {
            "condition": "Upper respiratory infection",
            "icd10": "J06.9",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Nasal congestion, sore throat, <3 weeks duration",
            "notes": "Self-limiting. Supportive care only.",
        },
        {
            "condition": "Asthma",
            "icd10": "J45.909",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Nighttime cough, wheezing, triggered by exercise or allergens",
            "notes": "Pulmonary function testing for diagnosis. Inhaler therapy.",
        },
        {
            "condition": "GERD-related cough",
            "icd10": "K21.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Chronic cough, worse lying down, heartburn, no fever",
            "notes": "PPI trial for 8 weeks. Lifestyle modifications.",
        },
        {
            "condition": "Lung cancer",
            "icd10": "C34.90",
            "urgency": "urgent",
            "likelihood": "less_common",
            "red_flags": "Persistent cough >3 weeks, hemoptysis, weight loss, smoking history",
            "notes": "CT chest for evaluation. Urgent pulmonology referral.",
        },
    ],
    "fatigue": [
        {
            "condition": "Iron deficiency anemia",
            "icd10": "D50.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Pale skin, weakness, shortness of breath on exertion",
            "notes": "CBC and iron studies. Investigate cause of iron loss.",
        },
        {
            "condition": "Hypothyroidism",
            "icd10": "E03.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Cold intolerance, weight gain, constipation, dry skin",
            "notes": "TSH blood test. Levothyroxine replacement if confirmed.",
        },
        {
            "condition": "Depression",
            "icd10": "F32.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Persistent sadness, loss of interest, sleep changes, appetite changes",
            "notes": "PHQ-9 screening. May need therapy and/or medication.",
        },
        {
            "condition": "Diabetes mellitus",
            "icd10": "E11.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Increased thirst, frequent urination, blurred vision",
            "notes": "Fasting glucose or HbA1c testing.",
        },
        {
            "condition": "Sleep apnea",
            "icd10": "G47.33",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Snoring, daytime sleepiness, morning headaches, obesity",
            "notes": "Sleep study for diagnosis. CPAP therapy if confirmed.",
        },
    ],
    "dizziness": [
        {
            "condition": "Benign positional vertigo (BPPV)",
            "icd10": "H81.10",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Brief episodes triggered by head position changes",
            "notes": "Epley maneuver is curative. Very common and benign.",
        },
        {
            "condition": "Orthostatic hypotension",
            "icd10": "I95.1",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Dizziness on standing, medication changes, dehydration",
            "notes": "Check orthostatic blood pressures. Review medications.",
        },
        {
            "condition": "Stroke/TIA",
            "icd10": "I63.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Sudden onset, facial droop, arm weakness, speech difficulty",
            "notes": "EMERGENCY. Call 911. Time-critical (tPA within 4.5 hours).",
        },
        {
            "condition": "Anemia",
            "icd10": "D64.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Fatigue, pallor, shortness of breath",
            "notes": "CBC for diagnosis. Investigate underlying cause.",
        },
    ],
    "nausea": [
        {
            "condition": "Gastroenteritis",
            "icd10": "K52.9",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Vomiting, diarrhea, recent food exposure",
            "notes": "Self-limiting. Hydration is key. Seek care if unable to keep fluids down.",
        },
        {
            "condition": "GERD",
            "icd10": "K21.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Heartburn, worse after meals",
            "notes": "Dietary modifications and PPI therapy.",
        },
        {
            "condition": "Medication side effect",
            "icd10": "T50.905A",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "New medication started recently, dose change",
            "notes": "Review all medications. Common with antibiotics, NSAIDs, opioids.",
        },
        {
            "condition": "Pregnancy",
            "icd10": "O21.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Morning nausea, missed period, reproductive age female",
            "notes": "Pregnancy test if applicable.",
        },
    ],
    "joint pain": [
        {
            "condition": "Osteoarthritis",
            "icd10": "M19.90",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Gradual onset, worse with activity, better with rest, age >50",
            "notes": "X-ray for diagnosis. NSAIDs, physical therapy, weight management.",
        },
        {
            "condition": "Rheumatoid arthritis",
            "icd10": "M06.9",
            "urgency": "soon",
            "likelihood": "less_common",
            "red_flags": "Symmetric joint involvement, morning stiffness >1 hour, swelling",
            "notes": "Rheumatology referral. RF and anti-CCP antibodies.",
        },
        {
            "condition": "Gout",
            "icd10": "M10.9",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Sudden onset, red/hot/swollen joint, often big toe, severe pain",
            "notes": "Uric acid level. Colchicine or NSAIDs for acute attack.",
        },
        {
            "condition": "Septic arthritis",
            "icd10": "M00.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Single hot swollen joint, fever, recent infection or surgery",
            "notes": "EMERGENCY. Joint aspiration for diagnosis. IV antibiotics.",
        },
    ],
    "skin rash": [
        {
            "condition": "Contact dermatitis",
            "icd10": "L25.9",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Itchy rash in area of contact with irritant/allergen",
            "notes": "Avoid trigger. Topical steroids for symptom relief.",
        },
        {
            "condition": "Drug reaction",
            "icd10": "L27.0",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "New medication, widespread rash, timing correlates with drug start",
            "notes": "Discontinue suspected drug. Watch for anaphylaxis signs.",
        },
        {
            "condition": "Cellulitis",
            "icd10": "L03.90",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Red, warm, spreading area, fever, tender to touch",
            "notes": "Bacterial skin infection. Oral or IV antibiotics needed.",
        },
        {
            "condition": "Anaphylaxis",
            "icd10": "T78.2",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Rapid onset, hives, swelling, difficulty breathing, known allergen exposure",
            "notes": "EMERGENCY. Epinephrine (EpiPen) immediately. Call 911.",
        },
    ],
    "back pain": [
        {
            "condition": "Mechanical low back pain",
            "icd10": "M54.5",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Related to movement/activity, no neurological symptoms",
            "notes": "Physical therapy, NSAIDs, activity modification. Most resolve in 4-6 weeks.",
        },
        {
            "condition": "Herniated disc",
            "icd10": "M51.16",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Radiating leg pain (sciatica), numbness, weakness",
            "notes": "MRI if symptoms persist >6 weeks. Physical therapy first line.",
        },
        {
            "condition": "Cauda equina syndrome",
            "icd10": "G83.4",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Saddle anesthesia, bowel/bladder dysfunction, bilateral leg weakness",
            "notes": "SURGICAL EMERGENCY. MRI urgently. Decompression within 48 hours.",
        },
        {
            "condition": "Kidney stones",
            "icd10": "N20.0",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Flank pain radiating to groin, colicky, blood in urine",
            "notes": "CT scan for diagnosis. Pain management and hydration.",
        },
    ],
    "palpitations": [
        {
            "condition": "Premature beats (PVCs/PACs)",
            "icd10": "I49.49",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Skipped beats, flutter sensation, no other symptoms",
            "notes": "Usually benign. ECG and Holter monitor for evaluation.",
        },
        {
            "condition": "Atrial fibrillation",
            "icd10": "I48.91",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Irregular rapid heartbeat, fatigue, shortness of breath, age >65",
            "notes": "ECG for diagnosis. Requires stroke risk assessment (CHA2DS2-VASc).",
        },
        {
            "condition": "Panic/anxiety disorder",
            "icd10": "F41.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Associated with anxiety, hyperventilation, no cardiac history",
            "notes": "Diagnosis of exclusion. Must rule out cardiac causes first.",
        },
        {
            "condition": "Hyperthyroidism",
            "icd10": "E05.90",
            "urgency": "soon",
            "likelihood": "less_common",
            "red_flags": "Weight loss, tremor, heat intolerance, anxiety",
            "notes": "TSH blood test. Endocrinology referral if confirmed.",
        },
    ],
    "frequent urination": [
        {
            "condition": "Urinary tract infection",
            "icd10": "N39.0",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Burning, urgency, cloudy/foul-smelling urine",
            "notes": "Urinalysis and culture. Antibiotics if confirmed.",
        },
        {
            "condition": "Diabetes mellitus",
            "icd10": "E11.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Increased thirst, weight loss, fatigue, blurred vision",
            "notes": "Fasting glucose or HbA1c. Polyuria is a cardinal symptom of diabetes.",
        },
        {
            "condition": "Benign prostatic hyperplasia",
            "icd10": "N40.0",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Male >50, weak stream, nocturia, hesitancy",
            "notes": "PSA screening. Alpha-blocker or 5-alpha reductase inhibitor therapy.",
        },
        {
            "condition": "Overactive bladder",
            "icd10": "N32.81",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Urgency, frequency, urge incontinence, no infection",
            "notes": "Bladder training, pelvic floor exercises, anticholinergic medications.",
        },
    ],
    "sore throat": [
        {
            "condition": "Viral pharyngitis",
            "icd10": "J02.9",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Gradual onset, cough, runny nose, mild fever",
            "notes": "Self-limiting. Supportive care. Antibiotics NOT indicated.",
        },
        {
            "condition": "Strep throat (Group A Strep)",
            "icd10": "J02.0",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Sudden onset, fever >101°F, tonsillar exudates, NO cough",
            "notes": "Rapid strep test. Penicillin/amoxicillin if positive.",
        },
        {
            "condition": "Peritonsillar abscess",
            "icd10": "J36",
            "urgency": "urgent",
            "likelihood": "less_common",
            "red_flags": "Severe unilateral throat pain, trismus, muffled voice, drooling",
            "notes": "ENT consultation. May need drainage.",
        },
    ],
    "swelling in legs": [
        {
            "condition": "Venous insufficiency",
            "icd10": "I87.2",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Bilateral, worse at end of day, varicose veins",
            "notes": "Compression stockings. Leg elevation. Weight management.",
        },
        {
            "condition": "Deep vein thrombosis (DVT)",
            "icd10": "I82.409",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Unilateral swelling, calf pain, warmth, recent immobility/surgery",
            "notes": "URGENT. Doppler ultrasound for diagnosis. Anticoagulation if confirmed.",
        },
        {
            "condition": "Heart failure",
            "icd10": "I50.9",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Bilateral, shortness of breath, weight gain, fatigue",
            "notes": "Echocardiogram and BNP levels. Cardiology referral.",
        },
        {
            "condition": "Medication side effect",
            "icd10": "T50.905A",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Amlodipine, NSAIDs, or corticosteroids recently started",
            "notes": "Review medication list. Amlodipine is a common cause of ankle edema.",
        },
    ],
    "weight loss": [
        {
            "condition": "Hyperthyroidism",
            "icd10": "E05.90",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Increased appetite despite weight loss, tremor, heat intolerance",
            "notes": "TSH testing. Endocrinology referral.",
        },
        {
            "condition": "Diabetes mellitus",
            "icd10": "E11.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Increased thirst and urination, fatigue",
            "notes": "Fasting glucose or HbA1c testing.",
        },
        {
            "condition": "Malignancy (cancer)",
            "icd10": "C80.1",
            "urgency": "urgent",
            "likelihood": "must_rule_out",
            "red_flags": "Unintentional >5% weight loss in 6 months, fatigue, night sweats",
            "notes": "Age-appropriate cancer screening. CBC, CMP, CT imaging.",
        },
        {
            "condition": "Depression",
            "icd10": "F32.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Decreased appetite, sadness, loss of interest",
            "notes": "PHQ-9 screening. Combined therapy and medication approach.",
        },
    ],
    "blurred vision": [
        {
            "condition": "Refractive error",
            "icd10": "H52.7",
            "urgency": "routine",
            "likelihood": "very_common",
            "red_flags": "Gradual onset, improved with squinting",
            "notes": "Eye exam and corrective lenses.",
        },
        {
            "condition": "Diabetic retinopathy",
            "icd10": "E11.319",
            "urgency": "urgent",
            "likelihood": "common",
            "red_flags": "Known diabetes, floaters, progressive vision loss",
            "notes": "Dilated eye exam. Ophthalmology referral. Glucose control critical.",
        },
        {
            "condition": "Acute angle-closure glaucoma",
            "icd10": "H40.21",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Sudden onset, eye pain, halos around lights, nausea, red eye",
            "notes": "EMERGENCY. Can cause permanent vision loss. Immediate ophthalmology.",
        },
        {
            "condition": "Stroke/TIA",
            "icd10": "I63.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Sudden onset, visual field loss, other neurological symptoms",
            "notes": "Call 911. Time-critical emergency.",
        },
    ],
    "numbness or tingling": [
        {
            "condition": "Peripheral neuropathy",
            "icd10": "G62.9",
            "urgency": "soon",
            "likelihood": "common",
            "red_flags": "Stocking-glove distribution, diabetes, alcohol use",
            "notes": "EMG/nerve conduction study. Treat underlying cause. Gabapentin for symptoms.",
        },
        {
            "condition": "Carpal tunnel syndrome",
            "icd10": "G56.00",
            "urgency": "routine",
            "likelihood": "common",
            "red_flags": "Hand/wrist numbness, worse at night, thumb-index-middle fingers",
            "notes": "Wrist splinting, ergonomic modifications. EMG for confirmation.",
        },
        {
            "condition": "Stroke/TIA",
            "icd10": "I63.9",
            "urgency": "emergency",
            "likelihood": "must_rule_out",
            "red_flags": "Sudden onset, one-sided, facial droop, speech difficulty",
            "notes": "EMERGENCY. Call 911 immediately. FAST criteria.",
        },
        {
            "condition": "Multiple sclerosis",
            "icd10": "G35",
            "urgency": "soon",
            "likelihood": "less_common",
            "red_flags": "Young adult, relapsing-remitting pattern, optic neuritis, fatigue",
            "notes": "MRI brain/spine. Neurology referral.",
        },
    ],
}


def lookup_symptoms(symptoms: list[str]) -> list[dict]:
    """Look up possible conditions for a list of symptoms.

    Args:
        symptoms: List of symptom descriptions.

    Returns:
        List of dicts with symptom, matched conditions, and overall urgency.
    """
    results = []
    for symptom in symptoms:
        symptom_lower = symptom.lower().strip()
        # Try exact match first, then partial match
        matched_conditions = None
        for key, conditions in SYMPTOM_CONDITIONS.items():
            if key == symptom_lower or symptom_lower in key or key in symptom_lower:
                matched_conditions = conditions
                break

        if matched_conditions:
            # Determine highest urgency among conditions
            urgency_order = {"emergency": 0, "urgent": 1, "soon": 2, "routine": 3}
            max_urgency = min(
                matched_conditions,
                key=lambda c: urgency_order.get(c["urgency"], 99),
            )
            results.append({
                "symptom": symptom,
                "matched": True,
                "conditions": matched_conditions,
                "highest_urgency": max_urgency["urgency"],
            })
        else:
            results.append({
                "symptom": symptom,
                "matched": False,
                "conditions": [],
                "highest_urgency": "unknown",
                "note": "Symptom not found in database. Please consult a healthcare provider for evaluation.",
            })

    return results
