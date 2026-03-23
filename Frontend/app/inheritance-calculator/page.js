"use client";

import React, { useMemo, useState } from "react";
import { Calculator } from "lucide-react";

const InheritanceCalculator = () => {
  const [deceasedGender, setDeceasedGender] = useState("male");

  const [heirs, setHeirs] = useState({
    husband: 0,
    wives: 1,
    sons: 0,
    daughters: 0,
    father: 0,
    mother: 0,
    grandfather: 0,
    grandmother: 0,
    uterineSiblings: 0,
    fullBrothers: 0,
    fullSisters: 0,
  });

  const [results, setResults] = useState(null);
  const [error, setError] = useState("");

  const labels = {
    husband: "Husband",
    wives: "Wives",
    sons: "Sons",
    daughters: "Daughters",
    father: "Father",
    mother: "Mother",
    grandfather: "Paternal Grandfather",
    grandmother: "Grandmother",
    uterineSiblings: "Maternal/Uterine Siblings",
    fullBrothers: "Full Brothers",
    fullSisters: "Full Sisters",
  };

  const handleHeirChange = (heir, value) => {
    let parsed = parseInt(value, 10);
    if (Number.isNaN(parsed) || parsed < 0) parsed = 0;

    if (heir === "husband") parsed = Math.min(parsed, 1);
    if (heir === "father") parsed = Math.min(parsed, 1);
    if (heir === "mother") parsed = Math.min(parsed, 1);
    if (heir === "grandfather") parsed = Math.min(parsed, 1);
    if (heir === "grandmother") parsed = Math.min(parsed, 1);
    if (heir === "wives") parsed = Math.min(parsed, 4);

    setHeirs((prev) => ({
      ...prev,
      [heir]: parsed,
    }));
  };

  const totalHeirs = useMemo(() => {
    return Object.values(heirs).reduce((sum, val) => sum + val, 0);
  }, [heirs]);

  const formatPercentage = (value) => {
    return `${(value * 100).toFixed(2)}%`;
  };

  const validateInputs = () => {
    if (totalHeirs === 0) {
      return "Please enter at least one heir.";
    }

    if (deceasedGender === "male" && heirs.husband > 0) {
      return "A deceased male cannot leave a husband.";
    }

    if (deceasedGender === "female" && heirs.wives > 0) {
      return "A deceased female cannot leave wives.";
    }

    if (deceasedGender === "male" && heirs.wives === 0) {
      return "For a deceased male, enter number of wives or set it to 0.";
    }

    if (deceasedGender === "female" && heirs.husband > 1) {
      return "A deceased female can have at most one husband.";
    }

    if (heirs.father > 0 && heirs.grandfather > 0) {
      return "Grandfather is excluded if father is alive.";
    }

    if (heirs.mother > 0 && heirs.grandmother > 0) {
      return "Grandmother is excluded if mother is alive.";
    }

    return "";
  };

  const calculateShares = () => {
    const validationError = validateInputs();
    if (validationError) {
      setError(validationError);
      setResults(null);
      return;
    }

    setError("");

    const shares = {};
    const details = {};

    const hasChildren = heirs.sons > 0 || heirs.daughters > 0;
    const hasMaleDescendants = heirs.sons > 0;

    const fatherExists = heirs.father > 0;
    const motherExists = heirs.mother > 0;
    const grandfatherExists = !fatherExists && heirs.grandfather > 0;
    const grandmotherExists = !motherExists && heirs.grandmother > 0;

    const totalSiblings =
      heirs.uterineSiblings + heirs.fullBrothers + heirs.fullSisters;

    const noAscendants = !fatherExists && !grandfatherExists;
    const noDescendants = !hasChildren;

    const hasSpouse =
      (deceasedGender === "male" && heirs.wives > 0) ||
      (deceasedGender === "female" && heirs.husband > 0);

    if (deceasedGender === "male" && heirs.wives > 0) {
      shares.wives = hasChildren ? 1 / 8 : 1 / 4;
      details.wives =
        heirs.wives === 1
          ? "Wife receives fixed share."
          : "All wives collectively share this fixed fraction equally.";
    }

    if (deceasedGender === "female" && heirs.husband > 0) {
      shares.husband = hasChildren ? 1 / 4 : 1 / 2;
      details.husband = "Husband receives fixed share.";
    }

    if (motherExists) {
      shares.mother = hasChildren || totalSiblings >= 2 ? 1 / 6 : 1 / 3;
      details.mother =
        hasChildren || totalSiblings >= 2
          ? "Mother gets 1/6 due to children or two/more siblings."
          : "Mother gets 1/3 in the absence of children and multiple siblings.";
    } else if (grandmotherExists) {
      shares.grandmother = 1 / 6;
      details.grandmother = "Grandmother substitutes mother in simplified rule.";
    }

    if (fatherExists && hasChildren) {
      shares.father = 1 / 6;
      details.father = "Father gets fixed 1/6 when deceased leaves children.";
    } else if (grandfatherExists && hasChildren) {
      shares.grandfather = 1 / 6;
      details.grandfather =
        "Paternal grandfather substitutes father in this simplified rule.";
    }

    if (heirs.daughters > 0 && !hasMaleDescendants) {
      shares.daughters = heirs.daughters === 1 ? 1 / 2 : 2 / 3;
      details.daughters =
        heirs.daughters === 1
          ? "Single daughter gets fixed 1/2 in absence of son."
          : "Two or more daughters collectively get 2/3 in absence of son.";
    }

    if (noAscendants && noDescendants && heirs.uterineSiblings > 0) {
      shares.uterineSiblings = heirs.uterineSiblings === 1 ? 1 / 6 : 1 / 3;
      details.uterineSiblings =
        heirs.uterineSiblings === 1
          ? "One uterine sibling gets 1/6."
          : "Two or more uterine siblings collectively get 1/3.";
    }

    if (motherExists && fatherExists && !hasChildren && totalSiblings === 0 && hasSpouse) {
      const spouseShare =
        deceasedGender === "male"
          ? heirs.wives > 0
            ? 1 / 4
            : 0
          : heirs.husband > 0
          ? 1 / 2
          : 0;

      shares.mother = (1 - spouseShare) / 3;
      details.mother =
        "Umariyya case applied: mother gets one-third of residue after spouse share.";

      delete shares.father;
      details.father = "Father will take the remaining residue after fixed shares.";
    }

    const fixedTotal = Object.values(shares).reduce((a, b) => a + b, 0);
    let residue = 1 - fixedTotal;

    if (residue < 0) residue = 0;

    if (heirs.sons > 0) {
      const totalUnits = heirs.sons * 2 + heirs.daughters;

      shares.sons = (residue * (heirs.sons * 2)) / totalUnits;
      details.sons = "Sons take residue as residuaries, each son = two daughters.";

      if (heirs.daughters > 0) {
        shares.daughters =
          (shares.daughters || 0) + (residue * heirs.daughters) / totalUnits;
        details.daughters =
          "Children share residue with ratio: male = 2, female = 1.";
      }
    } else if (fatherExists) {
      shares.father = (shares.father || 0) + residue;
      details.father = hasChildren
        ? "Father receives fixed 1/6 plus residue if any remains."
        : "Father takes residue as residuary.";
    } else if (grandfatherExists) {
      shares.grandfather = (shares.grandfather || 0) + residue;
      details.grandfather =
        "Grandfather takes residue in absence of father under this simplified rule.";
    } else if (
      noAscendants &&
      noDescendants &&
      (heirs.fullBrothers > 0 || heirs.fullSisters > 0)
    ) {
      const totalUnits = heirs.fullBrothers * 2 + heirs.fullSisters;

      if (totalUnits > 0) {
        if (heirs.fullBrothers > 0) {
          shares.fullBrothers =
            (residue * (heirs.fullBrothers * 2)) / totalUnits;
          details.fullBrothers =
            "Full brothers inherit residuary share when not blocked, at double full sisters.";
        }

        if (heirs.fullSisters > 0) {
          shares.fullSisters = (residue * heirs.fullSisters) / totalUnits;
          details.fullSisters =
            "Full sisters inherit with full brothers in 2:1 ratio in this simplified rule.";
        }
      }
    }

    const mappedResults = Object.entries(shares)
      .filter(([, value]) => value > 0)
      .map(([key, value]) => ({
        key,
        label:
          key === "wives"
            ? heirs.wives > 1
              ? `Wives (collective share for ${heirs.wives})`
              : "Wife"
            : key === "daughters"
            ? heirs.daughters > 1
              ? `Daughters (collective share for ${heirs.daughters})`
              : "Daughter"
            : key === "sons"
            ? heirs.sons > 1
              ? `Sons (collective share for ${heirs.sons})`
              : "Son"
            : key === "uterineSiblings"
            ? heirs.uterineSiblings > 1
              ? `Maternal/Uterine Siblings (collective share for ${heirs.uterineSiblings})`
              : "Maternal/Uterine Sibling"
            : key === "fullBrothers"
            ? heirs.fullBrothers > 1
              ? `Full Brothers (collective share for ${heirs.fullBrothers})`
              : "Full Brother"
            : key === "fullSisters"
            ? heirs.fullSisters > 1
              ? `Full Sisters (collective share for ${heirs.fullSisters})`
              : "Full Sister"
            : key.charAt(0).toUpperCase() + key.slice(1),
        fraction: value,
        details: details[key],
      }))
      .sort((a, b) => b.fraction - a.fraction);

    setResults(mappedResults);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <main className="max-w-3xl mx-auto px-6 lg:px-12 py-12">
        <div className="mb-8">
          <h1 className="text-3xl font-medium text-gray-900 mb-2 text-center">
            Basic Islamic Inheritance Calculator
          </h1>
          <p className="text-gray-600 text-center">
            Preliminary faraid estimate for common Pakistani Muslim cases
          </p>
        </div>

        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-blue-600/10 rounded-full flex items-center justify-center">
                <Calculator className="w-8 h-8 text-[#052379]" />
              </div>
            </div>
            <p className="text-gray-600 mb-2">
              Enter heir information and click Calculate to estimate inheritance shares.
            </p>
            <p className="text-sm text-red-600">
              Note: This is a preliminary calculator and should not be treated as final legal advice.
            </p>
          </div>

          <div className="bg-white border border-gray-200 rounded-2xl p-8">
            <div className="mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-1">
                Family Information
              </h2>
              <p className="text-gray-600">
                Distribution is assumed after funeral expenses, debts, and any valid bequest.
              </p>
            </div>

            <div className="space-y-6">
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-900">
                  Deceased Gender
                </label>

                <div className="flex flex-col gap-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="gender"
                      value="male"
                      checked={deceasedGender === "male"}
                      onChange={(e) => setDeceasedGender(e.target.value)}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-gray-900">Male</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="gender"
                      value="female"
                      checked={deceasedGender === "female"}
                      onChange={(e) => setDeceasedGender(e.target.value)}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-gray-900">Female</span>
                  </label>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-base font-normal text-gray-900">Heirs</h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {Object.keys(heirs).map((heirKey) => {
                    const hideForGender =
                      (deceasedGender === "male" && heirKey === "husband") ||
                      (deceasedGender === "female" && heirKey === "wives");

                    if (hideForGender) return null;

                    return (
                      <div key={heirKey} className="space-y-2">
                        <label className="block text-sm font-medium text-gray-900">
                          {labels[heirKey]}
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={heirs[heirKey]}
                          onChange={(e) => handleHeirChange(heirKey, e.target.value)}
                          className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                    );
                  })}
                </div>
              </div>

              {error && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <button
                onClick={calculateShares}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-[#052379] text-white rounded-lg font-medium hover:bg-[#041d5c] transition-colors"
              >
                <Calculator className="w-4 h-4" />
                Calculate Shares
              </button>
            </div>
          </div>

          {results && (
            <div className="bg-white border border-gray-200 rounded-2xl p-8">
              <h2 className="text-lg font-medium text-gray-900 mb-6">
                Inheritance Distribution
              </h2>

              <div className="space-y-4">
                {results.map((item) => (
                  <div
                    key={item.key}
                    className="py-3 border-b border-gray-100 last:border-0"
                  >
                    <div className="flex justify-between items-center gap-4">
                      <span className="text-gray-900 font-medium">{item.label}</span>
                      <span className="text-[#052379] font-semibold">
                        {formatPercentage(item.fraction)}
                      </span>
                    </div>
                    {item.details && (
                      <p className="mt-1 text-sm text-gray-500">{item.details}</p>
                    )}
                  </div>
                ))}
              </div>

              <div className="mt-6 rounded-xl bg-amber-50 border border-amber-200 p-4">
                <p className="text-sm text-amber-800">
                  This calculator covers common shares only. Complex Pakistani succession
                  matters, sect-based differences, orphan grandchildren, representation, wills,
                  and disputed heirship should be reviewed by a qualified lawyer or scholar.
                </p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default InheritanceCalculator;