# app/services/inheritance_service.py
"""
Islamic Inheritance (Faraid) Calculator — Pakistani law context.

Implements the core Quranic shares (fard) for primary heirs.
This is a simplified implementation covering the most common scenarios.
Complex cases (e.g. grandchildren, multiple levels of agnates) can be
extended here without touching the router.

References:
  - Muslim Personal Law (Shariat) Application Act 1937 (Pakistan)
  - Quranic verses: 4:11, 4:12, 4:176
"""
from fractions import Fraction
from typing import Dict, List, Tuple
from app import schemas


def calculate_inheritance(inp: schemas.HeirInput) -> schemas.InheritanceResult:
    """
    Returns each heir's fractional share and optional PKR amount.
    Implements Sunni Hanafi rules (default in Pakistan).
    """
    shares: Dict[str, Fraction] = {}
    notes: List[str] = []

    has_son = inp.sons > 0
    has_daughter = inp.daughters > 0
    has_child = has_son or has_daughter

    # ── Spouse ───────────────────────────────────────────────────────────────
    if inp.deceased_gender == "male":
        # Widow(s): 1/8 if children exist, else 1/4 — split equally
        if inp.spouse_count > 0:
            wife_share = Fraction(1, 8) if has_child else Fraction(1, 4)
            each_wife = wife_share / inp.spouse_count
            for i in range(inp.spouse_count):
                label = f"Wife {i+1}" if inp.spouse_count > 1 else "Wife"
                shares[label] = each_wife
    else:
        # Widower: 1/4 if children, else 1/2
        if inp.spouse_count > 0:
            shares["Husband"] = Fraction(1, 4) if has_child else Fraction(1, 2)

    # ── Parents ───────────────────────────────────────────────────────────────
    if inp.father_alive:
        if has_son:
            shares["Father"] = Fraction(1, 6)
        elif not has_child:
            # Father takes residue (asaba) — handled in residue step
            shares["Father"] = Fraction(0)  # placeholder, updated below
        else:
            # Only daughters: father gets 1/6 + residue
            shares["Father"] = Fraction(1, 6)

    if inp.mother_alive:
        if has_child or (inp.full_brothers + inp.full_sisters) >= 2:
            shares["Mother"] = Fraction(1, 6)
        else:
            shares["Mother"] = Fraction(1, 3)

    # ── Children ──────────────────────────────────────────────────────────────
    if has_son:
        # Sons + daughters: son = 2x daughter's share (asaba)
        pass  # Handled in residue below

    elif has_daughter and not has_son:
        if inp.daughters == 1:
            shares["Daughter"] = Fraction(1, 2)
        else:
            shares["Daughters"] = Fraction(2, 3)  # 2/3 split among all daughters

    # ── Residue (Asaba) ───────────────────────────────────────────────────────
    fixed_total = sum(v for v in shares.values() if v > 0)
    residue = Fraction(1) - fixed_total
    if residue < 0:
        residue = Fraction(0)
        notes.append("Warning: fixed shares exceed 100% — applying Awl (proportional reduction).")

    if has_son:
        # Sons + daughters: residue split (son = 2 × daughter)
        unit = residue / (2 * inp.sons + inp.daughters)
        if inp.sons == 1:
            shares["Son"] = unit * 2
        else:
            shares["Sons"] = unit * 2 * inp.sons  # total for all sons
        if has_daughter:
            shares["Daughter" if inp.daughters == 1 else "Daughters"] = unit * inp.daughters

    elif inp.father_alive and not has_child:
        # Father takes all residue
        shares["Father"] = residue

    elif inp.father_alive and has_daughter:
        # Father already has 1/6, add residue
        shares["Father"] = shares.get("Father", Fraction(0)) + residue

    elif residue > 0 and not has_child and not inp.father_alive:
        # Full brothers/sisters take residue
        if inp.full_brothers > 0 or inp.full_sisters > 0:
            unit = residue / (2 * inp.full_brothers + inp.full_sisters)
            if inp.full_brothers > 0:
                shares["Brother(s)"] = unit * 2 * inp.full_brothers
            if inp.full_sisters > 0:
                shares["Sister(s)"] = unit * inp.full_sisters
        elif inp.grandfather_alive:
            shares["Grandfather"] = residue
        else:
            notes.append("Remaining estate (Bait-ul-Mal) — no eligible residuary heirs.")

    # ── Grandfather (if no father) ────────────────────────────────────────────
    if inp.grandfather_alive and not inp.father_alive and not has_son:
        if "Grandfather" not in shares:
            if not has_child:
                shares["Grandfather"] = Fraction(1, 6)

    # ── Grandmother (if no mother) ────────────────────────────────────────────
    if inp.grandmother_alive and not inp.mother_alive:
        shares["Grandmother"] = Fraction(1, 6)

    # ── Awl: proportional reduction if total > 1 ─────────────────────────────
    total = sum(shares.values())
    if total > Fraction(1):
        notes.append("Awl applied: shares reduced proportionally.")
        shares = {k: v / total for k, v in shares.items()}
        total = Fraction(1)

    # ── Radd: redistribute surplus to fixed heirs (excluding husband/wife) ────
    total_after = sum(shares.values())
    surplus = Fraction(1) - total_after
    non_spouse_heirs = {k: v for k, v in shares.items() if k not in ("Wife", "Husband") and not k.startswith("Wife ")}
    if surplus > 0 and non_spouse_heirs:
        total_ns = sum(non_spouse_heirs.values())
        for key in non_spouse_heirs:
            if total_ns > 0:
                shares[key] += surplus * (shares[key] / total_ns)
        notes.append("Radd applied: surplus redistributed to non-spouse heirs.")

    # ── Build result ──────────────────────────────────────────────────────────
    heir_shares: List[schemas.HeirShare] = []
    for heir, frac in shares.items():
        if frac <= 0:
            continue
        pct = float(frac) * 100
        amount = float(frac) * inp.estate_value if inp.estate_value else None
        heir_shares.append(schemas.HeirShare(
            heir=heir,
            fraction=str(frac),
            percentage=round(pct, 4),
            amount=round(amount, 2) if amount is not None else None,
        ))

    heir_shares.sort(key=lambda x: -x.percentage)
    total_pct = sum(h.percentage for h in heir_shares)

    return schemas.InheritanceResult(
        shares=heir_shares,
        total_percentage=round(total_pct, 4),
        notes=notes,
    )
