"""
seed.py — Populate the database with sample data for development/testing.

Run with:  python seed.py
or from Backend root: python -m seed

This script is idempotent: it checks before inserting to avoid duplicates.
"""
import sys
import os

# Make sure the app package is on the path
sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
from app import models
from app.routers.auth import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()


def seed_users():
    users = [
        # Lawyers
        dict(email="ali.ahmed@lawgic.pk",     name="Advocate Ali Ahmed",     role="lawyer", phone_num="+923001111111"),
        dict(email="sara.khan@lawgic.pk",      name="Advocate Sara Khan",     role="lawyer", phone_num="+923002222222"),
        dict(email="fatima.ali@lawgic.pk",     name="Advocate Fatima Ali",    role="lawyer", phone_num="+923003333333"),
        dict(email="ahmed.malik@lawgic.pk",    name="Advocate Ahmed Malik",   role="lawyer", phone_num="+923004444444"),
        dict(email="hassan.raza@lawgic.pk",    name="Advocate Hassan Raza",   role="lawyer", phone_num="+923005555555"),
        # Clients
        dict(email="client1@lawgic.pk",        name="John Doe",               role="client", phone_num="+923111111111"),
        dict(email="client2@lawgic.pk",        name="Aisha Noor",             role="client", phone_num="+923222222222"),
    ]

    created = []
    for u in users:
        if db.query(models.User).filter(models.User.email == u["email"]).first():
            continue
        user = models.User(
            email=u["email"],
            name=u["name"],
            role=u["role"],
            phone_num=u["phone_num"],
            password_hash=hash_password("Password1"),  # default dev password
            is_active=True,
        )
        db.add(user)
        db.flush()
        created.append(user)
    db.commit()
    print(f"  Users: {len(created)} created.")
    return created


def seed_lawyer_profiles():
    profiles_data = [
        dict(
            email="ali.ahmed@lawgic.pk",
            specialization="Criminal Law,Civil Law",
            bio_data="Senior advocate with 15 years of experience in criminal defense and civil litigation in Lahore High Court.",
            verification_status="verified",
            years_of_experience=15,
            office_address="14-B Model Town, Lahore",
            city="Lahore",
            consultation_fee=5000,
            languages="Urdu,English",
            bar_council_number="L/12345/2009",
            law_school="Punjab University Law College",
            grad_year=2008,
            degree_type="LLB",
            average_rating=4.8,
            review_count=32,
        ),
        dict(
            email="sara.khan@lawgic.pk",
            specialization="Family Law,Civil Law",
            bio_data="Specializes in family matters including divorce, child custody, and property disputes. 12 years experience.",
            verification_status="verified",
            years_of_experience=12,
            office_address="Plot 22, F-7/2, Islamabad",
            city="Islamabad",
            consultation_fee=8000,
            languages="Urdu,English,Punjabi",
            bar_council_number="ISL/67890/2012",
            law_school="International Islamic University",
            grad_year=2011,
            degree_type="LLM",
            average_rating=4.9,
            review_count=47,
        ),
        dict(
            email="fatima.ali@lawgic.pk",
            specialization="Family Law,Immigration",
            bio_data="Dedicated to helping families navigate complex legal matters including divorce, custody, and immigration cases.",
            verification_status="verified",
            years_of_experience=8,
            office_address="Block 4, Clifton, Karachi",
            city="Karachi",
            consultation_fee=6000,
            languages="Urdu,English,Sindhi",
            bar_council_number="K/54321/2016",
            law_school="University of Karachi",
            grad_year=2015,
            degree_type="LLB",
            average_rating=4.7,
            review_count=24,
        ),
        dict(
            email="ahmed.malik@lawgic.pk",
            specialization="Corporate Law,Criminal Law",
            bio_data="Expert in criminal defense and corporate structuring. Former legal advisor to multinational corporations.",
            verification_status="verified",
            years_of_experience=15,
            office_address="Dolmen Mall, Karachi",
            city="Karachi",
            consultation_fee=15000,
            languages="Urdu,English",
            bar_council_number="K/11111/2009",
            law_school="Karachi University",
            grad_year=2008,
            degree_type="LLM",
            average_rating=4.9,
            review_count=89,
        ),
        dict(
            email="hassan.raza@lawgic.pk",
            specialization="Property Law,Civil Law",
            bio_data="Specializes in property disputes, land acquisition, and registration matters in Punjab.",
            verification_status="verified",
            years_of_experience=10,
            office_address="45-C, Gulberg III, Lahore",
            city="Lahore",
            consultation_fee=4000,
            languages="Urdu,Punjabi,English",
            bar_council_number="L/99999/2014",
            law_school="University of the Punjab",
            grad_year=2013,
            degree_type="LLB",
            average_rating=4.6,
            review_count=18,
        ),
    ]

    created = 0
    for pd in profiles_data:
        user = db.query(models.User).filter(models.User.email == pd["email"]).first()
        if not user:
            continue
        if db.get(models.LawyerProfile, user.user_id):
            continue
        profile = models.LawyerProfile(
            lawyer_id=user.user_id,
            specialization=pd["specialization"],
            bio_data=pd["bio_data"],
            verification_status=pd["verification_status"],
            years_of_experience=pd["years_of_experience"],
            office_address=pd["office_address"],
            city=pd["city"],
            consultation_fee=pd["consultation_fee"],
            languages=pd["languages"],
            bar_council_number=pd["bar_council_number"],
            law_school=pd["law_school"],
            grad_year=pd["grad_year"],
            degree_type=pd["degree_type"],
            average_rating=pd["average_rating"],
            review_count=pd["review_count"],
        )
        db.add(profile)
        created += 1
    db.commit()
    print(f"  Lawyer profiles: {created} created.")


def seed_reviews():
    clients = db.query(models.User).filter(models.User.role == "client").all()
    lawyers = db.query(models.LawyerProfile).all()
    if not clients or not lawyers:
        print("  Reviews: skipped (no clients or lawyers found)")
        return

    reviews_data = [
        (clients[0], lawyers[0], 5, "Excellent advocate! Very professional and knowledgeable. Highly recommend."),
        (clients[0], lawyers[1], 5, "Sara Khan helped me through a very difficult divorce case. Compassionate and thorough."),
        (clients[0], lawyers[2], 4, "Good service. Handled my immigration case efficiently."),
    ]
    if len(clients) > 1:
        reviews_data += [
            (clients[1], lawyers[0], 5, "Ali Ahmed is the best criminal lawyer in Lahore. Cleared my case completely!"),
            (clients[1], lawyers[3], 5, "Ahmed Malik saved our company from a major legal dispute. Outstanding."),
        ]

    created = 0
    for client, lawyer, stars, comment in reviews_data:
        existing = db.query(models.RatingReview).filter(
            models.RatingReview.user_id == client.user_id,
            models.RatingReview.lawyer_id == lawyer.lawyer_id,
        ).first()
        if existing:
            continue
        db.add(models.RatingReview(
            user_id=client.user_id,
            lawyer_id=lawyer.lawyer_id,
            stars=stars,
            comment=comment,
        ))
        created += 1
    db.commit()
    print(f"  Reviews: {created} created.")


def seed_document_templates():
    templates = [
        dict(
            type="fir",
            language="en",
            title="First Information Report (FIR)",
            description="Standard FIR template for lodging a complaint with police in Pakistan.",
            fields_schema='{"complainant_name":"string","cnic":"string","incident_date":"date","incident_location":"string","accused_name":"string","incident_description":"string"}',
            sample_content="""FIRST INFORMATION REPORT (FIR)

To,
The Station House Officer,
Police Station: {{police_station}}

Subject: Complaint regarding criminal matter

Respected Sir,

I, {{complainant_name}}, CNIC No. {{cnic}}, hereby report the following:

On {{incident_date}}, at {{incident_location}}, the following incident occurred:

{{incident_description}}

The accused person(s): {{accused_name}}

I request that appropriate legal action be taken.

Complainant: {{complainant_name}}
Date: {{incident_date}}
""",
        ),
        dict(
            type="tenancy_agreement",
            language="en",
            title="Tenancy Agreement",
            description="Standard residential tenancy agreement compliant with Pakistani law.",
            fields_schema='{"landlord_name":"string","tenant_name":"string","property_address":"string","monthly_rent":"number","start_date":"date","duration_months":"number","advance_months":"number"}',
            sample_content="""TENANCY AGREEMENT

This agreement is made on {{start_date}} between:

LANDLORD: {{landlord_name}}
TENANT: {{tenant_name}}

PROPERTY: {{property_address}}

TERMS:
1. Monthly Rent: PKR {{monthly_rent}}
2. Duration: {{duration_months}} months starting from {{start_date}}
3. Advance Rent: {{advance_months}} months
4. The tenant shall maintain the property in good condition.
5. Either party may terminate with 30 days written notice.

Signed:
Landlord: _______________     Tenant: _______________
""",
        ),
        dict(
            type="divorce_notice",
            language="en",
            title="Divorce Notice (Talaq)",
            description="Legal divorce notice under Muslim Family Laws Ordinance 1961.",
            fields_schema='{"husband_name":"string","wife_name":"string","nikah_date":"date","witnesses":"string"}',
            sample_content="""DIVORCE NOTICE
Under Muslim Family Laws Ordinance 1961

I, {{husband_name}}, hereby pronounce Talaq upon my wife {{wife_name}}.

Our Nikah was solemnized on {{nikah_date}}.

This notice is being sent to the Chairman, Union Council as required by law.

Witnesses: {{witnesses}}

Signed: {{husband_name}}
Date: [Date]
""",
        ),
        dict(
            type="affidavit",
            language="en",
            title="General Affidavit",
            description="General purpose affidavit template.",
            fields_schema='{"deponent_name":"string","cnic":"string","address":"string","statement":"string"}',
            sample_content="""AFFIDAVIT

I, {{deponent_name}}, CNIC No. {{cnic}}, resident of {{address}}, do hereby solemnly affirm and declare as under:

{{statement}}

I solemnly affirm that the above statement is true to the best of my knowledge and belief.

Deponent: {{deponent_name}}
Date: [Date]

SWORN before me this _____ day of __________, ______
Oath Commissioner / Notary Public
""",
        ),
        dict(
            type="power_of_attorney",
            language="en",
            title="Power of Attorney",
            description="General Power of Attorney template for Pakistani courts.",
            fields_schema='{"principal_name":"string","principal_cnic":"string","attorney_name":"string","attorney_cnic":"string","powers":"string"}',
            sample_content="""GENERAL POWER OF ATTORNEY

Know all men by these presents that I, {{principal_name}}, CNIC No. {{principal_cnic}}, do hereby appoint {{attorney_name}}, CNIC No. {{attorney_cnic}}, as my true and lawful attorney to act on my behalf.

Powers granted: {{powers}}

This Power of Attorney shall remain in force until revoked in writing.

Principal: {{principal_name}}
Date: [Date]
""",
        ),
    ]

    created = 0
    for t in templates:
        if db.query(models.DocumentTemplate).filter(models.DocumentTemplate.type == t["type"]).first():
            continue
        db.add(models.DocumentTemplate(**t))
        created += 1
    db.commit()
    print(f"  Document templates: {created} created.")


def seed_sample_conversation():
    client = db.query(models.User).filter(models.User.email == "client1@lawgic.pk").first()
    lawyer_user = db.query(models.User).filter(models.User.email == "ali.ahmed@lawgic.pk").first()
    if not client or not lawyer_user:
        print("  Sample conversation: skipped")
        return

    # Check if conversation already exists
    my_convs = {
        p.conv_id for p in db.query(models.ConversationParticipant)
        .filter(models.ConversationParticipant.user_id == client.user_id)
        .all()
    }
    other_convs = {
        p.conv_id for p in db.query(models.ConversationParticipant)
        .filter(models.ConversationParticipant.user_id == lawyer_user.user_id)
        .all()
    }
    if my_convs & other_convs:
        print("  Sample conversation: already exists")
        return

    conv = models.Conversation()
    db.add(conv)
    db.flush()

    db.add(models.ConversationParticipant(conv_id=conv.conv_id, user_id=client.user_id))
    db.add(models.ConversationParticipant(conv_id=conv.conv_id, user_id=lawyer_user.user_id))

    messages = [
        (client.user_id, "Assalam o Alaikum, I need legal advice regarding a property dispute."),
        (lawyer_user.user_id, "Walaikum Assalam, I can certainly help. Please describe the situation."),
        (client.user_id, "My neighbor has encroached on part of my land in Lahore. What are my options?"),
        (lawyer_user.user_id, "You have several options: file a civil suit for possession, lodge a complaint with the local administration, or approach the Lahore Development Authority. I recommend we first review your title documents."),
        (client.user_id, "Thank you. When can we meet?"),
    ]
    for sender_id, content in messages:
        db.add(models.Message(conv_id=conv.conv_id, sender_id=sender_id, content=content))

    db.commit()
    print("  Sample conversation: created.")


if __name__ == "__main__":
    print("Seeding database...")
    seed_users()
    seed_lawyer_profiles()
    seed_reviews()
    seed_document_templates()
    seed_sample_conversation()
    db.close()
    print("Done.")
