"""Mock FHIR data for deployed version (no OpenEMR dependency).

10 patients with realistic medical histories, 5 practitioners,
PractitionerRole mappings, and sample appointments.
All data is in FHIR R4 format matching what OpenEMR returns.
"""

# ── Patients ─────────────────────────────────────────────────────────────────

PATIENTS = [
    {
        "resourceType": "Patient",
        "id": "p-john-smith",
        "name": [{"given": ["John"], "family": "Smith"}],
        "birthDate": "1965-03-15",
        "gender": "male",
        "telecom": [{"system": "phone", "value": "555-0101"}],
        "address": [{"line": ["123 Main St"], "city": "Austin", "state": "TX", "postalCode": "78701"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-sarah-johnson",
        "name": [{"given": ["Sarah"], "family": "Johnson"}],
        "birthDate": "1988-07-22",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "555-0102"}],
        "address": [{"line": ["456 Oak Ave"], "city": "Austin", "state": "TX", "postalCode": "78702"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-robert-chen",
        "name": [{"given": ["Robert"], "family": "Chen"}],
        "birthDate": "1952-11-08",
        "gender": "male",
        "telecom": [{"system": "phone", "value": "555-0103"}],
        "address": [{"line": ["789 Elm Dr"], "city": "Austin", "state": "TX", "postalCode": "78703"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-maria-garcia",
        "name": [{"given": ["Maria"], "family": "Garcia"}],
        "birthDate": "1975-01-30",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "555-0104"}],
        "address": [{"line": ["321 Pine Ln"], "city": "Austin", "state": "TX", "postalCode": "78704"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-james-williams",
        "name": [{"given": ["James"], "family": "Williams"}],
        "birthDate": "1960-09-12",
        "gender": "male",
        "telecom": [{"system": "phone", "value": "555-0105"}],
        "address": [{"line": ["654 Cedar Blvd"], "city": "Austin", "state": "TX", "postalCode": "78705"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-emily-rodriguez",
        "name": [{"given": ["Emily"], "family": "Rodriguez"}],
        "birthDate": "1992-04-18",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "555-0106"}],
        "address": [{"line": ["987 Birch Way"], "city": "Austin", "state": "TX", "postalCode": "78706"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-michael-thompson",
        "name": [{"given": ["Michael"], "family": "Thompson"}],
        "birthDate": "1980-12-03",
        "gender": "male",
        "telecom": [{"system": "phone", "value": "555-0107"}],
        "address": [{"line": ["147 Maple Ct"], "city": "Austin", "state": "TX", "postalCode": "78707"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-lisa-anderson",
        "name": [{"given": ["Lisa"], "family": "Anderson"}],
        "birthDate": "1995-06-25",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "555-0108"}],
        "address": [{"line": ["258 Walnut St"], "city": "Austin", "state": "TX", "postalCode": "78708"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-david-martinez",
        "name": [{"given": ["David"], "family": "Martinez"}],
        "birthDate": "1970-08-14",
        "gender": "male",
        "telecom": [{"system": "phone", "value": "555-0109"}],
        "address": [{"line": ["369 Spruce Rd"], "city": "Austin", "state": "TX", "postalCode": "78709"}],
    },
    {
        "resourceType": "Patient",
        "id": "p-jennifer-wilson",
        "name": [{"given": ["Jennifer"], "family": "Wilson"}],
        "birthDate": "1985-02-28",
        "gender": "female",
        "telecom": [{"system": "phone", "value": "555-0110"}],
        "address": [{"line": ["480 Aspen Pl"], "city": "Austin", "state": "TX", "postalCode": "78710"}],
    },
]

# ── Conditions (keyed by patient ID) ─────────────────────────────────────────

CONDITIONS = [
    # John Smith
    {"id": "c-001", "code": {"coding": [{"code": "E11.9", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Type 2 Diabetes Mellitus"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-john-smith"}, "onsetDateTime": "2010-06-15"},
    {"id": "c-002", "code": {"coding": [{"code": "I10", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Essential Hypertension"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-john-smith"}, "onsetDateTime": "2012-03-20"},
    # Sarah Johnson
    {"id": "c-003", "code": {"coding": [{"code": "J45.20", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Mild Intermittent Asthma"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-sarah-johnson"}, "onsetDateTime": "2005-09-10"},
    {"id": "c-004", "code": {"coding": [{"code": "F41.1", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Generalized Anxiety Disorder"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-sarah-johnson"}, "onsetDateTime": "2018-01-15"},
    # Robert Chen
    {"id": "c-005", "code": {"coding": [{"code": "I25.10", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Coronary Artery Disease (CAD)"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-robert-chen"}, "onsetDateTime": "2015-04-22"},
    {"id": "c-006", "code": {"coding": [{"code": "I48.91", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Atrial Fibrillation"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-robert-chen"}, "onsetDateTime": "2017-08-03"},
    {"id": "c-007", "code": {"coding": [{"code": "K21.0", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Gastroesophageal Reflux Disease (GERD)"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-robert-chen"}, "onsetDateTime": "2019-02-14"},
    # Maria Garcia
    {"id": "c-008", "code": {"coding": [{"code": "M06.9", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Rheumatoid Arthritis"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-maria-garcia"}, "onsetDateTime": "2016-11-05"},
    {"id": "c-009", "code": {"coding": [{"code": "M81.0", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Osteoporosis"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-maria-garcia"}, "onsetDateTime": "2020-03-18"},
    # James Williams
    {"id": "c-010", "code": {"coding": [{"code": "J44.1", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Chronic Obstructive Pulmonary Disease (COPD)"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-james-williams"}, "onsetDateTime": "2014-07-22"},
    {"id": "c-011", "code": {"coding": [{"code": "F32.1", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Major Depressive Disorder"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-james-williams"}, "onsetDateTime": "2019-10-01"},
    # Emily Rodriguez
    {"id": "c-012", "code": {"coding": [{"code": "E03.9", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Hypothyroidism"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-emily-rodriguez"}, "onsetDateTime": "2020-05-12"},
    {"id": "c-013", "code": {"coding": [{"code": "G43.909", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Migraine, Unspecified"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-emily-rodriguez"}, "onsetDateTime": "2018-08-30"},
    # Michael Thompson
    {"id": "c-014", "code": {"coding": [{"code": "E10.9", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Type 1 Diabetes Mellitus"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-michael-thompson"}, "onsetDateTime": "1995-03-01"},
    {"id": "c-015", "code": {"coding": [{"code": "I10", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Essential Hypertension"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-michael-thompson"}, "onsetDateTime": "2018-06-20"},
    # Lisa Anderson
    {"id": "c-016", "code": {"coding": [{"code": "F41.1", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Generalized Anxiety Disorder"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-lisa-anderson"}, "onsetDateTime": "2021-02-14"},
    {"id": "c-017", "code": {"coding": [{"code": "K58.9", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Irritable Bowel Syndrome (IBS)"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-lisa-anderson"}, "onsetDateTime": "2020-09-05"},
    # David Martinez
    {"id": "c-018", "code": {"coding": [{"code": "M10.9", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Gout"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-david-martinez"}, "onsetDateTime": "2017-12-10"},
    {"id": "c-019", "code": {"coding": [{"code": "E78.5", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Hyperlipidemia"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-david-martinez"}, "onsetDateTime": "2019-04-22"},
    # Jennifer Wilson
    {"id": "c-020", "code": {"coding": [{"code": "G40.909", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Epilepsy, Unspecified"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-jennifer-wilson"}, "onsetDateTime": "2010-07-15"},
    {"id": "c-021", "code": {"coding": [{"code": "F32.1", "system": "http://hl7.org/fhir/sid/icd-10-cm", "display": "Major Depressive Disorder"}]}, "clinicalStatus": {"coding": [{"code": "active"}]}, "subject": {"reference": "Patient/p-jennifer-wilson"}, "onsetDateTime": "2022-01-20"},
]

# ── Medication Requests (keyed by patient) ───────────────────────────────────

MEDICATION_REQUESTS = [
    # John Smith
    {"id": "m-001", "medicationCodeableConcept": {"coding": [{"display": "Metformin 500mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-john-smith"}, "note": [{"text": "500mg twice daily with meals"}]},
    {"id": "m-002", "medicationCodeableConcept": {"coding": [{"display": "Lisinopril 10mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-john-smith"}, "note": [{"text": "10mg once daily"}]},
    {"id": "m-003", "medicationCodeableConcept": {"coding": [{"display": "Atorvastatin 20mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-john-smith"}, "note": [{"text": "20mg once daily at bedtime"}]},
    # Sarah Johnson
    {"id": "m-004", "medicationCodeableConcept": {"coding": [{"display": "Albuterol Inhaler"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-sarah-johnson"}, "note": [{"text": "2 puffs every 4-6 hours as needed"}]},
    {"id": "m-005", "medicationCodeableConcept": {"coding": [{"display": "Sertraline 50mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-sarah-johnson"}, "note": [{"text": "50mg once daily in the morning"}]},
    # Robert Chen
    {"id": "m-006", "medicationCodeableConcept": {"coding": [{"display": "Warfarin 5mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-robert-chen"}, "note": [{"text": "5mg once daily, monitor INR"}]},
    {"id": "m-007", "medicationCodeableConcept": {"coding": [{"display": "Metoprolol 50mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-robert-chen"}, "note": [{"text": "50mg twice daily"}]},
    {"id": "m-008", "medicationCodeableConcept": {"coding": [{"display": "Omeprazole 20mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-robert-chen"}, "note": [{"text": "20mg once daily before breakfast"}]},
    {"id": "m-009", "medicationCodeableConcept": {"coding": [{"display": "Aspirin 81mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-robert-chen"}, "note": [{"text": "81mg once daily"}]},
    # Maria Garcia
    {"id": "m-010", "medicationCodeableConcept": {"coding": [{"display": "Methotrexate 15mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-maria-garcia"}, "note": [{"text": "15mg once weekly"}]},
    {"id": "m-011", "medicationCodeableConcept": {"coding": [{"display": "Folic Acid 1mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-maria-garcia"}, "note": [{"text": "1mg daily"}]},
    {"id": "m-012", "medicationCodeableConcept": {"coding": [{"display": "Alendronate 70mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-maria-garcia"}, "note": [{"text": "70mg once weekly on empty stomach"}]},
    # James Williams
    {"id": "m-013", "medicationCodeableConcept": {"coding": [{"display": "Tiotropium 18mcg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-james-williams"}, "note": [{"text": "18mcg inhaled once daily"}]},
    {"id": "m-014", "medicationCodeableConcept": {"coding": [{"display": "Fluticasone/Salmeterol 250/50"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-james-williams"}, "note": [{"text": "1 inhalation twice daily"}]},
    {"id": "m-015", "medicationCodeableConcept": {"coding": [{"display": "Bupropion 150mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-james-williams"}, "note": [{"text": "150mg once daily"}]},
    # Emily Rodriguez
    {"id": "m-016", "medicationCodeableConcept": {"coding": [{"display": "Levothyroxine 75mcg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-emily-rodriguez"}, "note": [{"text": "75mcg once daily on empty stomach"}]},
    {"id": "m-017", "medicationCodeableConcept": {"coding": [{"display": "Sumatriptan 50mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-emily-rodriguez"}, "note": [{"text": "50mg as needed for migraine, max 200mg/day"}]},
    # Michael Thompson
    {"id": "m-018", "medicationCodeableConcept": {"coding": [{"display": "Insulin Glargine 20 units"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-michael-thompson"}, "note": [{"text": "20 units subcutaneous once daily at bedtime"}]},
    {"id": "m-019", "medicationCodeableConcept": {"coding": [{"display": "Lisinopril 20mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-michael-thompson"}, "note": [{"text": "20mg once daily"}]},
    # Lisa Anderson
    {"id": "m-020", "medicationCodeableConcept": {"coding": [{"display": "Sertraline 100mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-lisa-anderson"}, "note": [{"text": "100mg once daily"}]},
    {"id": "m-021", "medicationCodeableConcept": {"coding": [{"display": "Dicyclomine 20mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-lisa-anderson"}, "note": [{"text": "20mg four times daily before meals"}]},
    # David Martinez
    {"id": "m-022", "medicationCodeableConcept": {"coding": [{"display": "Allopurinol 300mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-david-martinez"}, "note": [{"text": "300mg once daily"}]},
    {"id": "m-023", "medicationCodeableConcept": {"coding": [{"display": "Rosuvastatin 10mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-david-martinez"}, "note": [{"text": "10mg once daily"}]},
    # Jennifer Wilson
    {"id": "m-024", "medicationCodeableConcept": {"coding": [{"display": "Levetiracetam 500mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-jennifer-wilson"}, "note": [{"text": "500mg twice daily"}]},
    {"id": "m-025", "medicationCodeableConcept": {"coding": [{"display": "Fluoxetine 20mg"}]}, "status": "active", "intent": "order", "subject": {"reference": "Patient/p-jennifer-wilson"}, "note": [{"text": "20mg once daily in the morning"}]},
]

# ── Allergy Intolerances ─────────────────────────────────────────────────────

ALLERGIES = [
    # John Smith
    {"id": "a-001", "code": {"coding": [{"display": "Penicillin"}], "text": "Penicillin"}, "type": "allergy", "category": ["medication"], "criticality": "high", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-john-smith"}},
    # Sarah Johnson
    {"id": "a-002", "code": {"coding": [{"display": "Sulfa Drugs"}], "text": "Sulfa Drugs"}, "type": "allergy", "category": ["medication"], "criticality": "high", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-sarah-johnson"}},
    {"id": "a-003", "code": {"coding": [{"display": "Latex"}], "text": "Latex"}, "type": "allergy", "category": ["environment"], "criticality": "low", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-sarah-johnson"}},
    # Maria Garcia
    {"id": "a-004", "code": {"coding": [{"display": "NSAIDs"}], "text": "NSAIDs"}, "type": "allergy", "category": ["medication"], "criticality": "high", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-maria-garcia"}},
    # James Williams
    {"id": "a-005", "code": {"coding": [{"display": "Codeine"}], "text": "Codeine"}, "type": "allergy", "category": ["medication"], "criticality": "moderate", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-james-williams"}},
    # Emily Rodriguez
    {"id": "a-006", "code": {"coding": [{"display": "Iodine Contrast"}], "text": "Iodine Contrast"}, "type": "allergy", "category": ["medication"], "criticality": "high", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-emily-rodriguez"}},
    # Lisa Anderson
    {"id": "a-007", "code": {"coding": [{"display": "Amoxicillin"}], "text": "Amoxicillin"}, "type": "allergy", "category": ["medication"], "criticality": "moderate", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-lisa-anderson"}},
    # Jennifer Wilson
    {"id": "a-008", "code": {"coding": [{"display": "Carbamazepine"}], "text": "Carbamazepine"}, "type": "allergy", "category": ["medication"], "criticality": "high", "clinicalStatus": {"coding": [{"code": "active"}]}, "patient": {"reference": "Patient/p-jennifer-wilson"}},
]

# ── Practitioners ────────────────────────────────────────────────────────────

PRACTITIONERS = [
    {
        "resourceType": "Practitioner",
        "id": "pr-sarah-wilson",
        "name": [{"given": ["Sarah"], "family": "Wilson", "prefix": ["Dr."]}],
        "active": True,
        "telecom": [{"system": "phone", "value": "555-0201"}, {"system": "email", "value": "swilson@austinfamily.med"}],
        "address": [{"line": ["100 Medical Pkwy"], "city": "Austin", "state": "TX", "postalCode": "78750"}],
    },
    {
        "resourceType": "Practitioner",
        "id": "pr-michael-brown",
        "name": [{"given": ["Michael"], "family": "Brown", "prefix": ["Dr."]}],
        "active": True,
        "telecom": [{"system": "phone", "value": "555-0202"}, {"system": "email", "value": "mbrown@austinheart.med"}],
        "address": [{"line": ["200 Heart Center Dr"], "city": "Austin", "state": "TX", "postalCode": "78751"}],
    },
    {
        "resourceType": "Practitioner",
        "id": "pr-emily-davis",
        "name": [{"given": ["Emily"], "family": "Davis", "prefix": ["Dr."]}],
        "active": True,
        "telecom": [{"system": "phone", "value": "555-0203"}, {"system": "email", "value": "edavis@austinderm.med"}],
        "address": [{"line": ["300 Skin Care Blvd"], "city": "Austin", "state": "TX", "postalCode": "78752"}],
    },
    {
        "resourceType": "Practitioner",
        "id": "pr-james-park",
        "name": [{"given": ["James"], "family": "Park", "prefix": ["Dr."]}],
        "active": True,
        "telecom": [{"system": "phone", "value": "555-0204"}, {"system": "email", "value": "jpark@austininternal.med"}],
        "address": [{"line": ["400 Wellness Ave"], "city": "Austin", "state": "TX", "postalCode": "78753"}],
    },
    {
        "resourceType": "Practitioner",
        "id": "pr-rachel-green",
        "name": [{"given": ["Rachel"], "family": "Green", "prefix": ["Dr."]}],
        "active": True,
        "telecom": [{"system": "phone", "value": "555-0205"}, {"system": "email", "value": "rgreen@austinpeds.med"}],
        "address": [{"line": ["500 Children's Way"], "city": "Austin", "state": "TX", "postalCode": "78754"}],
    },
]

# ── Practitioner Roles ───────────────────────────────────────────────────────

PRACTITIONER_ROLES = [
    {
        "id": "role-001",
        "practitioner": {"reference": "Practitioner/pr-sarah-wilson", "display": "Dr. Sarah Wilson"},
        "specialty": [{"coding": [{"code": "207Q00000X", "display": "Family Medicine"}]}],
        "organization": {"display": "Austin Family Health Center"},
    },
    {
        "id": "role-002",
        "practitioner": {"reference": "Practitioner/pr-michael-brown", "display": "Dr. Michael Brown"},
        "specialty": [{"coding": [{"code": "207RC0000X", "display": "Cardiovascular Disease"}]}],
        "organization": {"display": "Austin Heart Institute"},
    },
    {
        "id": "role-003",
        "practitioner": {"reference": "Practitioner/pr-emily-davis", "display": "Dr. Emily Davis"},
        "specialty": [{"coding": [{"code": "207N00000X", "display": "Dermatology"}]}],
        "organization": {"display": "Austin Dermatology Associates"},
    },
    {
        "id": "role-004",
        "practitioner": {"reference": "Practitioner/pr-james-park", "display": "Dr. James Park"},
        "specialty": [{"coding": [{"code": "207R00000X", "display": "Internal Medicine"}]}],
        "organization": {"display": "Austin Internal Medicine Group"},
    },
    {
        "id": "role-005",
        "practitioner": {"reference": "Practitioner/pr-rachel-green", "display": "Dr. Rachel Green"},
        "specialty": [{"coding": [{"code": "208000000X", "display": "Pediatrics"}]}],
        "organization": {"display": "Austin Pediatrics Center"},
    },
]

# ── Appointments (sample booked) ─────────────────────────────────────────────

APPOINTMENTS = [
    {
        "id": "appt-001",
        "status": "booked",
        "start": "2026-02-25T09:00:00",
        "end": "2026-02-25T09:30:00",
        "participant": [
            {"actor": {"reference": "Practitioner/pr-sarah-wilson", "display": "Dr. Sarah Wilson"}},
            {"actor": {"reference": "Patient/p-john-smith", "display": "John Smith"}},
        ],
    },
    {
        "id": "appt-002",
        "status": "booked",
        "start": "2026-02-25T10:00:00",
        "end": "2026-02-25T10:30:00",
        "participant": [
            {"actor": {"reference": "Practitioner/pr-sarah-wilson", "display": "Dr. Sarah Wilson"}},
            {"actor": {"reference": "Patient/p-lisa-anderson", "display": "Lisa Anderson"}},
        ],
    },
    {
        "id": "appt-003",
        "status": "booked",
        "start": "2026-02-25T14:00:00",
        "end": "2026-02-25T14:30:00",
        "participant": [
            {"actor": {"reference": "Practitioner/pr-michael-brown", "display": "Dr. Michael Brown"}},
            {"actor": {"reference": "Patient/p-robert-chen", "display": "Robert Chen"}},
        ],
    },
    {
        "id": "appt-004",
        "status": "booked",
        "start": "2026-02-25T11:00:00",
        "end": "2026-02-25T11:30:00",
        "participant": [
            {"actor": {"reference": "Practitioner/pr-emily-davis", "display": "Dr. Emily Davis"}},
            {"actor": {"reference": "Patient/p-maria-garcia", "display": "Maria Garcia"}},
        ],
    },
    {
        "id": "appt-005",
        "status": "booked",
        "start": "2026-02-26T09:30:00",
        "end": "2026-02-26T10:00:00",
        "participant": [
            {"actor": {"reference": "Practitioner/pr-michael-brown", "display": "Dr. Michael Brown"}},
            {"actor": {"reference": "Patient/p-james-williams", "display": "James Williams"}},
        ],
    },
    {
        "id": "appt-006",
        "status": "booked",
        "start": "2026-02-26T13:00:00",
        "end": "2026-02-26T13:30:00",
        "participant": [
            {"actor": {"reference": "Practitioner/pr-sarah-wilson", "display": "Dr. Sarah Wilson"}},
            {"actor": {"reference": "Patient/p-emily-rodriguez", "display": "Emily Rodriguez"}},
        ],
    },
]

# ── Immunizations ────────────────────────────────────────────────────────────

IMMUNIZATIONS = [
    {"id": "imm-001", "vaccineCode": {"coding": [{"display": "Influenza Vaccine"}]}, "occurrenceDateTime": "2025-10-15", "status": "completed", "patient": {"reference": "Patient/p-john-smith"}},
    {"id": "imm-002", "vaccineCode": {"coding": [{"display": "COVID-19 Vaccine (Pfizer)"}]}, "occurrenceDateTime": "2025-09-01", "status": "completed", "patient": {"reference": "Patient/p-john-smith"}},
    {"id": "imm-003", "vaccineCode": {"coding": [{"display": "Influenza Vaccine"}]}, "occurrenceDateTime": "2025-10-20", "status": "completed", "patient": {"reference": "Patient/p-sarah-johnson"}},
    {"id": "imm-004", "vaccineCode": {"coding": [{"display": "Tdap Vaccine"}]}, "occurrenceDateTime": "2024-05-10", "status": "completed", "patient": {"reference": "Patient/p-robert-chen"}},
    {"id": "imm-005", "vaccineCode": {"coding": [{"display": "Pneumococcal Vaccine"}]}, "occurrenceDateTime": "2025-03-22", "status": "completed", "patient": {"reference": "Patient/p-robert-chen"}},
]

# ── Observations (vitals/labs) ───────────────────────────────────────────────

OBSERVATIONS = [
    {"id": "obs-001", "code": {"coding": [{"code": "4548-4", "display": "Hemoglobin A1c"}]}, "valueQuantity": {"value": 7.2, "unit": "%"}, "status": "final", "effectiveDateTime": "2026-01-15", "subject": {"reference": "Patient/p-john-smith"}, "referenceRange": [{"low": {"value": 4.0, "unit": "%"}, "high": {"value": 5.6, "unit": "%"}}]},
    {"id": "obs-002", "code": {"coding": [{"code": "8480-6", "display": "Systolic Blood Pressure"}]}, "valueQuantity": {"value": 138, "unit": "mmHg"}, "status": "final", "effectiveDateTime": "2026-02-01", "subject": {"reference": "Patient/p-john-smith"}},
    {"id": "obs-003", "code": {"coding": [{"code": "2093-3", "display": "Total Cholesterol"}]}, "valueQuantity": {"value": 195, "unit": "mg/dL"}, "status": "final", "effectiveDateTime": "2026-01-15", "subject": {"reference": "Patient/p-john-smith"}, "referenceRange": [{"low": {"value": 0, "unit": "mg/dL"}, "high": {"value": 200, "unit": "mg/dL"}}]},
    {"id": "obs-004", "code": {"coding": [{"code": "6299-2", "display": "INR"}]}, "valueQuantity": {"value": 2.5, "unit": "INR"}, "status": "final", "effectiveDateTime": "2026-02-10", "subject": {"reference": "Patient/p-robert-chen"}, "referenceRange": [{"low": {"value": 2.0, "unit": "INR"}, "high": {"value": 3.0, "unit": "INR"}}]},
]
