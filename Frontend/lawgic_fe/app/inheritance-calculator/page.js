"use client";
import React, { useState } from 'react';
import { Calculator } from 'lucide-react';

const InheritanceCalculator = () => {
  const [deceasedGender, setDeceasedGender] = useState('male');
  const [heirs, setHeirs] = useState({
    spouse: 1,
    sons: 0,
    daughters: 0,
    father: 0,
    mother: 0,
    grandfather: 0,
    grandmother: 0,
    siblings: 0
  });
  const [results, setResults] = useState(null);

  const handleHeirChange = (heir, value) => {
    setHeirs(prev => ({
      ...prev,
      [heir]: parseInt(value) || 0
    }));
  };

  const calculateShares = () => {
    
    const totalHeirs = Object.values(heirs).reduce((sum, val) => sum + val, 0);
    
    if (totalHeirs === 0) {
      alert('Please add at least one heir');
      return;
    }

    const shares = {};
    const hasChildren = heirs.sons > 0 || heirs.daughters > 0;
    const hasMaleDescendants = heirs.sons > 0;
    const hasMultipleSiblings = heirs.siblings > 1; 
    const fatherExists = heirs.father > 0;
    const motherExists = heirs.mother > 0;

    if (heirs.spouse > 0) {
      if (deceasedGender === 'male') {
        shares.spouse = hasChildren ? 1/8 : 1/4;
      } else {
        shares.spouse = hasChildren ? 1/4 : 1/2;
      }
    }

    if (motherExists) {
       shares.mother = (hasChildren || hasMultipleSiblings) ? 1/6 : 1/3;
    }

    if (!motherExists && heirs.grandmother > 0) {
      shares.grandmother = 1/6;
    }

     if (fatherExists && hasChildren) {
      shares.father = 1/6;
    }

     if (!fatherExists && heirs.grandfather > 0 && hasChildren) {
      shares.grandfather = 1/6;
    }

    if (heirs.daughters > 0 && !hasMaleDescendants) {
      if (heirs.daughters === 1) {
        shares.daughters = 1/2;
      } else {
        shares.daughters = 2/3;
      }
    }

   const currentTotal = Object.values(shares).reduce((a, b) => a + b, 0);
    let residue = 1 - currentTotal;
    
     if (residue < 0) residue = 0;

    if (heirs.sons > 0) {
      const maleWeight = 2;
      const femaleWeight = 1;
      const totalUnits = (heirs.sons * maleWeight) + (heirs.daughters * femaleWeight);
      
      shares.sons = (residue * (heirs.sons * maleWeight)) / totalUnits;
      
      if (heirs.daughters > 0) {
        shares.daughters = (residue * (heirs.daughters * femaleWeight)) / totalUnits;
      }

    } else if (fatherExists) {
       shares.father = (shares.father || 0) + residue;

    } else if (heirs.grandfather > 0) {
      shares.grandfather = (shares.grandfather || 0) + residue;

    } else if (heirs.siblings > 0) {
      shares.siblings = residue;
    }

    setResults(shares);
  };

  const formatPercentage = (value) => {
    if (!value) return '0%';
    return (value * 100).toFixed(2) + '%';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      
      <main className="max-w-2xl mx-auto px-6 lg:px-12 py-12">
      
        <div className="mb-8">
          <h1 className="text-3xl font-medium text-gray-900 mb-2">
            Islamic Inheritance Calculator (Faraid)
          </h1>
          <p className="text-gray-600">
            Calculate shares according to Islamic law
          </p>
        </div>

   
        <div className="space-y-6">
       
          <div className="bg-white border border-gray-200 rounded-2xl p-8 text-center">
            <div className="flex justify-center mb-6">
              <div className="w-16 h-16 bg-blue-600/10 rounded-full flex items-center justify-center">
                <Calculator className="w-8 h-8 text-[#052379]" />
              </div>
            </div>
            <p className="text-gray-600">
              Enter heir information and click Calculate to see the distribution
            </p>
          </div>

       
          <div className="bg-white border border-gray-200 rounded-2xl p-8">
         
            <div className="mb-8">
              <h2 className="text-lg font-medium text-gray-900 mb-1">
                Family Information
              </h2>
              <p className="text-gray-600">
                Enter information about the heirs of the subject
              </p>
            </div>

            <div className="space-y-6">

              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-900">
                  Deceased Gender
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="gender"
                      value="male"
                      checked={deceasedGender === 'male'}
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
                      checked={deceasedGender === 'female'}
                      onChange={(e) => setDeceasedGender(e.target.value)}
                      className="w-4 h-4 text-blue-600 border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-gray-900">Female</span>
                  </label>
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="text-base font-normal text-gray-900">Heirs</h3>
                
                <div className="grid grid-cols-2 gap-4">
               
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Spouse
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.spouse}
                      onChange={(e) => handleHeirChange('spouse', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Sons
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.sons}
                      onChange={(e) => handleHeirChange('sons', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Daughters
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.daughters}
                      onChange={(e) => handleHeirChange('daughters', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Father
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.father}
                      onChange={(e) => handleHeirChange('father', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                
                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Mother
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.mother}
                      onChange={(e) => handleHeirChange('mother', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Grandfather
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.grandfather}
                      onChange={(e) => handleHeirChange('grandfather', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Siblings
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.siblings}
                      onChange={(e) => handleHeirChange('siblings', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-sm font-medium text-gray-900">
                      Grandmother
                    </label>
                    <input
                      type="number"
                      min="0"
                      value={heirs.grandmother}
                      onChange={(e) => handleHeirChange('grandmother', e.target.value)}
                      className="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={calculateShares}
                className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-[#052379] text-white rounded-lg font-medium hover:bg-[#041d5c] transition-colors"
              >
                <Calculator className="w-4 h-4" />
                Calculate Shares
              </button>
            </div>
          </div>

          {/* Results */}
          {results && (
            <div className="bg-white border border-gray-200 rounded-2xl p-8">
              <h2 className="text-lg font-medium text-gray-900 mb-6">
                Inheritance Distribution
              </h2>
              <div className="space-y-4">
                {Object.entries(results).map(([heir, share]) => (
                  <div key={heir} className="flex justify-between items-center py-3 border-b border-gray-100 last:border-0">
                    <span className="text-gray-900 font-medium capitalize">
                      {heir}
                    </span>
                    <span className="text-[#052379] font-semibold">
                      {formatPercentage(share)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
};

export default InheritanceCalculator;