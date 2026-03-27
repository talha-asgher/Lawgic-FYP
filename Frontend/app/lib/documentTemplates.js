
export const DOCUMENT_TEMPLATES = {

  fir: {
    key: "fir",
    title: "FIR (First Information Report)",
    subtitle: "Draft a police complaint for cognizable offenses",
    legalBasis: "Section 154 Cr.P.C 1898",
    color: "red",
    sections: [
      {
        heading: "Complainant Information",
        fields: [
          { name: "complainant_name",  label: "Complainant Full Name",      type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "cnic",              label: "CNIC Number",                type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "father_name",       label: "Father's / Husband's Name",  type: "text",     required: true,  placeholder: "Full name" },
          { name: "caste",             label: "Caste / Biradari",           type: "text",     required: false, placeholder: "e.g. Mughal, Rajput (optional)" },
          { name: "occupation",        label: "Occupation",                 type: "text",     required: false, placeholder: "e.g. Business, Service" },
          { name: "phone",             label: "Mobile Number",              type: "text",     required: true,  placeholder: "03XX-XXXXXXX" },
          { name: "address",           label: "Residential Address",        type: "textarea", required: true,  placeholder: "House No., Street, Mohalla, City" },
        ]
      },
      {
        heading: "Incident Details",
        fields: [
          { name: "police_station",    label: "Police Station",             type: "text",     required: true,  placeholder: "e.g. Gulberg Police Station" },
          { name: "district",          label: "District",                   type: "text",     required: true,  placeholder: "e.g. Lahore" },
          { name: "province",          label: "Province",                   type: "select",   required: true,  options: ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory", "Azad Kashmir", "Gilgit-Baltistan"] },
          { name: "incident_date",     label: "Date of Incident",           type: "date",     required: true  },
          { name: "incident_time",     label: "Time of Incident",           type: "time",     required: false },
          { name: "incident_location", label: "Exact Location of Incident", type: "text",     required: true,  placeholder: "Street, Mohalla, Area where offense occurred" },
        ]
      },
      {
        heading: "Offense & Accused Details",
        fields: [
          { name: "ppc_sections",      label: "Relevant PPC Sections",      type: "text",     required: false, placeholder: "e.g. 302 (Murder), 392 (Robbery), 354 (Assault)" },
          { name: "offense_details",   label: "Full Details of Offense",    type: "textarea", required: true,  placeholder: "Describe what happened in complete detail — who, what, when, where, how..." },
          { name: "accused_name",      label: "Accused Name(s)",            type: "text",     required: false, placeholder: "Full name(s), leave blank if unknown" },
          { name: "accused_father",    label: "Accused Father's Name",      type: "text",     required: false, placeholder: "If known" },
          { name: "accused_address",   label: "Accused Address",            type: "text",     required: false, placeholder: "If known" },
          { name: "accused_desc",      label: "Accused Description",        type: "text",     required: false, placeholder: "Height, complexion, age, clothing (if unknown person)" },
          { name: "witnesses",         label: "Witness Name(s) & Address",  type: "textarea", required: false, placeholder: "Full name and address of each witness" },
          { name: "property_lost",     label: "Property / Items Lost (if any)", type: "textarea", required: false, placeholder: "Description and estimated value of stolen/damaged items" },
        ]
      }
    ]
  },

  tenancy: {
    key: "tenancy",
    title: "Tenancy Agreement",
    subtitle: "Standard rental agreement for landlords and tenants",
    legalBasis: "Rent Restriction Ordinance 2001",
    color: "blue",
    sections: [
      {
        heading: "Landlord Information",
        fields: [
          { name: "landlord_name",     label: "Landlord Full Name",         type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "landlord_cnic",     label: "Landlord CNIC",              type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "landlord_father",   label: "Landlord Father's Name",     type: "text",     required: true },
          { name: "landlord_phone",    label: "Landlord Mobile",            type: "text",     required: true,  placeholder: "03XX-XXXXXXX" },
          { name: "landlord_address",  label: "Landlord Permanent Address", type: "textarea", required: true },
        ]
      },
      {
        heading: "Tenant Information",
        fields: [
          { name: "tenant_name",        label: "Tenant Full Name",          type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "tenant_cnic",        label: "Tenant CNIC",               type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "tenant_father_name", label: "Tenant Father's Name",      type: "text",     required: true },
          { name: "tenant_phone",       label: "Tenant Mobile",             type: "text",     required: true,  placeholder: "03XX-XXXXXXX" },
          { name: "tenant_occupation",  label: "Tenant Occupation",         type: "text",     required: false, placeholder: "e.g. Service, Business" },
          { name: "tenant_address",     label: "Tenant Permanent Address",  type: "textarea", required: true,  placeholder: "Permanent address (may differ from rented property)" },
        ]
      },
      {
        heading: "Property & Rent Details",
        fields: [
          { name: "property_address",  label: "Rented Property Address",   type: "textarea", required: true,  placeholder: "Complete address with House No., Street, Mohalla, City" },
          { name: "property_type",     label: "Property Type",             type: "select",   required: true,  options: ["Residential House", "Apartment/Flat", "Upper Portion", "Ground Floor Portion", "Shop/Commercial", "Office", "Warehouse", "Plaza"] },
          { name: "property_area",     label: "Property Area",             type: "text",     required: false, placeholder: "e.g. 5 Marla, 10 Marla, 1 Kanal" },
          { name: "monthly_rent",      label: "Monthly Rent (PKR)",        type: "number",   required: true,  placeholder: "e.g. 25000" },
          { name: "rent_in_words",     label: "Rent in Words",             type: "text",     required: true,  placeholder: "e.g. Twenty Five Thousand Rupees Only" },
          { name: "security_deposit",  label: "Security Deposit (PKR)",    type: "number",   required: true,  placeholder: "e.g. 50000" },
          { name: "advance_months",    label: "Advance Months Paid",       type: "number",   required: false, placeholder: "e.g. 2" },
          { name: "lease_duration",    label: "Lease Duration (Months)",   type: "number",   required: true,  placeholder: "e.g. 12" },
          { name: "start_date",        label: "Lease Start Date",          type: "date",     required: true  },
          { name: "rent_payment_day",  label: "Rent Due Day (each month)", type: "number",   required: true,  placeholder: "e.g. 5 (5th of each month)" },
          { name: "utilities",         label: "Utilities Responsibility",  type: "select",   required: true,  options: ["All utilities paid by tenant", "Electricity included in rent", "Gas included in rent", "Water included in rent", "All utilities included in rent"] },
          { name: "stamp_paper_value", label: "Stamp Paper Value (PKR)",   type: "select",   required: true,  options: ["100", "200", "500", "1000", "2000"] },
          { name: "special_conditions",label: "Special Conditions",        type: "textarea", required: false, placeholder: "e.g. No subletting, no commercial use, pets policy..." },
        ]
      }
    ]
  },

  divorce: {
    key: "divorce",
    title: "Divorce Notice (Talaq)",
    subtitle: "Legal notice for dissolution of marriage under MFLO 1961",
    legalBasis: "Muslim Family Laws Ordinance 1961 — Section 7",
    color: "amber",
    sections: [
      {
        heading: "Husband's Information",
        fields: [
          { name: "husband_name",    label: "Husband Full Name",          type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "husband_cnic",    label: "Husband CNIC",               type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "husband_father",  label: "Husband's Father Name",      type: "text",     required: true },
          { name: "husband_address", label: "Husband's Current Address",  type: "textarea", required: true },
          { name: "husband_phone",   label: "Husband's Mobile",           type: "text",     required: false, placeholder: "03XX-XXXXXXX" },
        ]
      },
      {
        heading: "Wife's Information",
        fields: [
          { name: "wife_name",       label: "Wife Full Name",             type: "text",     required: true,  placeholder: "As per CNIC / Nikah Nama" },
          { name: "wife_cnic",       label: "Wife CNIC",                  type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "wife_father",     label: "Wife's Father Name",         type: "text",     required: true },
          { name: "wife_address",    label: "Wife's Current Address",     type: "textarea", required: true,  placeholder: "Address where notice copy will be sent" },
        ]
      },
      {
        heading: "Nikah & Divorce Details",
        fields: [
          { name: "nikah_date",        label: "Date of Nikah",              type: "date",     required: true },
          { name: "nikah_registrar",   label: "Nikah Registrar (Qazi) Name",type: "text",     required: true },
          { name: "nikah_reg_number",  label: "Nikah Registration Number",  type: "text",     required: false, placeholder: "From Nikah Nama certificate" },
          { name: "nikah_place",       label: "Place of Nikah",             type: "text",     required: false, placeholder: "City / District" },
          { name: "union_council",     label: "Union Council Name & Number",type: "text",     required: true,  placeholder: "e.g. UC-15, Gulberg Town, Lahore" },
          { name: "uc_address",        label: "Union Council Address",      type: "textarea", required: true,  placeholder: "Full address of Union Council" },
          { name: "city",              label: "City",                       type: "text",     required: true },
          { name: "talaq_type",        label: "Type of Talaq",              type: "select",   required: true,  options: [
            "Talaq-e-Ahsan (Single revocable Talaq — 3 months iddat)",
            "Talaq-e-Hasan (Three Talaqs over 3 months — revocable)",
            "Talaq-ul-Bain (Irrevocable — requires Halalah)",
            "Khula (Wife's request — initiated by wife)"
          ]},
          { name: "talaq_date",        label: "Date Talaq Was Pronounced",  type: "date",     required: true },
          { name: "mehr_amount",       label: "Mehr Amount (PKR)",          type: "text",     required: false, placeholder: "As per Nikah Nama — husband must pay if not yet paid" },
          { name: "mehr_status",       label: "Mehr Payment Status",        type: "select",   required: false, options: ["Already paid at time of Nikah", "Paid in full now", "Partially paid", "Unpaid — to be paid"] },
          { name: "children",          label: "Number of Children (if any)",type: "number",   required: false, placeholder: "0 if none" },
          { name: "reason",            label: "Reason for Divorce (Optional)", type: "textarea", required: false },
        ]
      }
    ]
  },


  affidavit: {
    key: "affidavit",
    title: "Affidavit",
    subtitle: "Sworn legal statement on stamp paper before Oath Commissioner",
    legalBasis: "Qanoon-e-Shahadat Order 1984 / Oaths Act 1873",
    color: "green",
    sections: [
      {
        heading: "Deponent Information",
        fields: [
          { name: "deponent_name",       label: "Deponent Full Name",        type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "deponent_cnic",       label: "Deponent CNIC",             type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "deponent_father",     label: "Father's / Husband's Name", type: "text",     required: true },
          { name: "deponent_age",        label: "Age",                       type: "number",   required: true,  placeholder: "e.g. 35" },
          { name: "deponent_occupation", label: "Occupation",                type: "text",     required: true,  placeholder: "e.g. Government Service, Business, Student" },
          { name: "deponent_religion",   label: "Religion",                  type: "select",   required: true,  options: ["Islam", "Christianity", "Hinduism", "Other"] },
          { name: "deponent_address",    label: "Residential Address",       type: "textarea", required: true,  placeholder: "House No., Street, Mohalla, City" },
        ]
      },
      {
        heading: "Affidavit Details",
        fields: [
          { name: "court_authority",  label: "Before (Court / Authority)",  type: "text",     required: false, placeholder: "e.g. Senior Civil Judge Lahore / NADRA / Registrar LHC" },
          { name: "case_number",      label: "Case / Reference Number",     type: "text",     required: false, placeholder: "If related to a court case" },
          { name: "subject",          label: "Subject of Affidavit",        type: "text",     required: true,  placeholder: "e.g. Declaration of Name Change / Property Ownership / Income" },
          { name: "statement",        label: "Statement / Declaration",     type: "textarea", required: true,  placeholder: "Write each point as a separate paragraph. e.g:\n1. That I am a citizen of Pakistan...\n2. That I am the owner of...\n3. That the above facts are true..." },
          { name: "date",             label: "Date",                        type: "date",     required: true },
          { name: "city",             label: "City / District",             type: "text",     required: true },
          { name: "stamp_paper_value",label: "Stamp Paper Value (PKR)",     type: "select",   required: true,  options: ["50", "100", "200", "500"] },
        ]
      }
    ]
  },

  poa: {
    key: "poa",
    title: "Power of Attorney",
    subtitle: "Authorize someone to act on your behalf — requires Notary / Sub-Registrar",
    legalBasis: "Powers of Attorney Act 1882 / Registration Act 1908",
    color: "purple",
    sections: [
      {
        heading: "Principal (Grantor) Information",
        fields: [
          { name: "principal_name",    label: "Principal Full Name",        type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "principal_cnic",    label: "Principal CNIC",             type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "principal_father",  label: "Father's Name",              type: "text",     required: true },
          { name: "principal_age",     label: "Age",                        type: "number",   required: true,  placeholder: "Must be 18+ to grant POA" },
          { name: "principal_address", label: "Principal Address",          type: "textarea", required: true },
          { name: "principal_phone",   label: "Principal Mobile",           type: "text",     required: false, placeholder: "03XX-XXXXXXX" },
        ]
      },
      {
        heading: "Attorney (Grantee) Information",
        fields: [
          { name: "attorney_name",     label: "Attorney Full Name",         type: "text",     required: true,  placeholder: "As per CNIC" },
          { name: "attorney_cnic",     label: "Attorney CNIC",              type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "attorney_father",   label: "Attorney Father's Name",     type: "text",     required: true },
          { name: "attorney_relation", label: "Relation to Principal",      type: "text",     required: true,  placeholder: "e.g. Son, Brother, Advocate, Friend" },
          { name: "attorney_address",  label: "Attorney Address",           type: "textarea", required: true },
        ]
      },
      {
        heading: "Powers & Validity",
        fields: [
          { name: "poa_type",             label: "Type of POA",               type: "select",   required: true,  options: [
            "General Power of Attorney (all matters)",
            "Special Power of Attorney (specific matter only)",
            "Irrevocable Power of Attorney (cannot be cancelled)"
          ]},
          { name: "powers_granted",       label: "Powers Granted",            type: "textarea", required: true,  placeholder: "e.g.\n- To sell/purchase property at [address]\n- To appear before courts\n- To sign documents on my behalf\n- To collect dues/payments" },
          { name: "property_description", label: "Property Description (if property-related)", type: "textarea", required: false, placeholder: "Khasra No., Khata No., Mouza, Tehsil, District OR House No., Street, City" },
          { name: "limitations",          label: "Limitations / Restrictions", type: "textarea", required: false, placeholder: "Any specific restrictions on the attorney's powers" },
          { name: "validity",             label: "Validity / Duration",        type: "text",     required: true,  placeholder: "e.g. Valid for 1 year from date / Until revoked in writing / Permanent" },
          { name: "date",                 label: "Date of Execution",          type: "date",     required: true },
          { name: "city",                 label: "City",                       type: "text",     required: true },
          { name: "registration_required",label: "Registration",               type: "select",   required: true,  options: [
            "To be registered with Sub-Registrar (recommended for property)",
            "To be attested by Notary Public only",
            "To be attested by Pakistani Embassy/Consulate (if abroad)"
          ]},
        ]
      }
    ]
  },


  legal_notice: {
    key: "legal_notice",
    title: "Legal Notice",
    subtitle: "Formal pre-litigation notice — sent via registered post",
    legalBasis: "Code of Civil Procedure 1908 (CPC)",
    color: "slate",
    sections: [
      {
        heading: "Sender / Complainant Information",
        fields: [
          { name: "sender_name",     label: "Sender Full Name",            type: "text",     required: true },
          { name: "sender_cnic",     label: "Sender CNIC",                 type: "text",     required: true,  placeholder: "XXXXX-XXXXXXX-X" },
          { name: "sender_address",  label: "Sender Address",              type: "textarea", required: true },
          { name: "sender_phone",    label: "Sender Phone",                type: "text",     required: true,  placeholder: "03XX-XXXXXXX" },
          { name: "advocate_name",   label: "Advocate Name (if through lawyer)", type: "text", required: false, placeholder: "Adv. [Full Name]" },
          { name: "advocate_bar",    label: "Bar Council Enrollment No.",  type: "text",     required: false, placeholder: "e.g. PLB-12345 (Punjab Bar Council)" },
          { name: "advocate_address",label: "Advocate Office Address",     type: "textarea", required: false },
        ]
      },
      {
        heading: "Recipient Information",
        fields: [
          { name: "recipient_name",    label: "Recipient Full Name / Company",  type: "text",     required: true },
          { name: "recipient_address", label: "Recipient Complete Address",      type: "textarea", required: true,  placeholder: "Full address for registered post delivery" },
          { name: "recipient_cnic",    label: "Recipient CNIC (if individual)", type: "text",     required: false, placeholder: "XXXXX-XXXXXXX-X" },
        ]
      },
      {
        heading: "Notice Details",
        fields: [
          { name: "notice_subject",   label: "Subject of Notice",          type: "text",     required: true,  placeholder: "e.g. Recovery of Amount / Breach of Contract / Wrongful Termination" },
          { name: "legal_basis",      label: "Legal Basis / Relevant Law", type: "text",     required: false, placeholder: "e.g. Contract Act 1872, Section 73 / PPC Section 420" },
          { name: "facts",            label: "Statement of Facts",         type: "textarea", required: true,  placeholder: "Chronological facts — dates, amounts, agreements, defaults..." },
          { name: "demand",           label: "Demand / Relief Sought",     type: "textarea", required: true,  placeholder: "Specific demand: payment of PKR X / restoration / specific performance..." },
          { name: "compliance_days",  label: "Days to Comply",             type: "select",   required: true,  options: ["7", "14", "15", "30", "45", "60"] },
          { name: "consequence",      label: "Consequence of Non-Compliance", type: "textarea", required: false, placeholder: "e.g. Civil suit / Criminal complaint / Both civil and criminal proceedings" },
          { name: "date",             label: "Date of Notice",             type: "date",     required: true },
          { name: "city",             label: "City",                       type: "text",     required: true },
        ]
      }
    ]
  }
};

export const TEMPLATE_LIST = Object.values(DOCUMENT_TEMPLATES);

export const TEMPLATE_COLORS = {
  red:    { bg: "bg-red-500/10",    icon: "text-red-500",    border: "hover:border-red-200",    badge: "bg-red-50 text-red-700" },
  blue:   { bg: "bg-blue-600/10",   icon: "text-blue-600",   border: "hover:border-blue-200",   badge: "bg-blue-50 text-blue-700" },
  amber:  { bg: "bg-amber-500/10",  icon: "text-amber-500",  border: "hover:border-amber-200",  badge: "bg-amber-50 text-amber-700" },
  green:  { bg: "bg-green-600/10",  icon: "text-green-600",  border: "hover:border-green-200",  badge: "bg-green-50 text-green-700" },
  purple: { bg: "bg-purple-500/10", icon: "text-purple-600", border: "hover:border-purple-200", badge: "bg-purple-50 text-purple-700" },
  slate:  { bg: "bg-slate-500/10",  icon: "text-slate-600",  border: "hover:border-slate-200",  badge: "bg-slate-50 text-slate-700" },
};