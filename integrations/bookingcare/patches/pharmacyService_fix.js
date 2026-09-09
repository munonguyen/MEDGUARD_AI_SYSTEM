/**
 * BookingCare Patch: Fix Safety Flaw 1 (Fail-Open Pharmacy Matching)
 *
 * Target File: BE/src/services/pharmacyService.js
 * Vulnerable Lines: ~520-523
 *
 * VULNERABILITY ANALYSIS:
 * In the legacy pharmacyService.findBestMedicineMatch implementation:
 * - If keyword matching failed, the 'else' fallback assigned:
 *     match = PHARMACY_CATALOG[0]; // "Default to high quality Panadol Extra or Berocca"
 * - In addition, generic keywords were dangerously mapped:
 *     "kháng sinh" -> Augmentin 625
 *     "giảm đau"   -> Panadol Extra
 * Consequence: An unrecognized drug name (or OCR mistake) silently dispensed an arbitrary drug.
 *
 * SOLUTION (Fail-Closed, Principle P4):
 * 1. Remove the fallback assignment of PHARMACY_CATALOG[0].
 * 2. Return null when similarity is below threshold (0.85).
 * 3. Return a candidates list for pharmacist human review.
 */

// =========================================================================
// PATCHED IMPLEMENTATION FOR BE/src/services/pharmacyService.js
// =========================================================================

function normalizeText(text) {
  if (!text) return "";
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\w\s]/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Calculates string similarity ratio (Dice coefficient / Levenshtein equivalent)
 */
function calculateSimilarity(str1, str2) {
  const s1 = normalizeText(str1);
  const s2 = normalizeText(str2);
  if (s1 === s2) return 1.0;
  if (!s1 || !s2) return 0.0;

  const pairs1 = new Set();
  for (let i = 0; i < s1.length - 1; i++) pairs1.add(s1.slice(i, i + 2));
  let intersection = 0;
  for (let i = 0; i < s2.length - 1; i++) {
    if (pairs1.has(s2.slice(i, i + 2))) intersection++;
  }
  return (2.0 * intersection) / (s1.length + s2.length - 2);
}

/**
 * Safely find best medicine match from catalog without fail-open fallback.
 *
 * @param {string} medicineName - Name extracted from prescription
 * @param {Array} catalog - Pharmacy catalog items
 * @param {number} [threshold=0.85] - Strict minimum similarity score
 * @returns {Object} { matchedProduct: Object|null, similarity: number, candidates: Array, requiresReview: boolean }
 */
function findBestMedicineMatchSafe(medicineName, catalog = [], threshold = 0.85) {
  if (!medicineName || !catalog || catalog.length === 0) {
    return {
      matchedProduct: null,
      similarity: 0.0,
      candidates: [],
      requiresReview: true,
      reason: "EMPTY_INPUT_OR_CATALOG",
    };
  }

  const queryNorm = normalizeText(medicineName);

  // 1. Exact match check
  for (const item of catalog) {
    const itemNameNorm = normalizeText(item.name || item.product_name);
    const itemIngNorm = normalizeText(item.active_ingredient || "");
    if (queryNorm === itemNameNorm || (itemIngNorm && queryNorm === itemIngNorm)) {
      return {
        matchedProduct: item,
        similarity: 1.0,
        candidates: [],
        requiresReview: false,
        matchType: "EXACT",
      };
    }
  }

  // 2. Fuzzy similarity ranking
  const scored = catalog.map((item) => {
    const nameScore = calculateSimilarity(medicineName, item.name || item.product_name || "");
    const ingScore = calculateSimilarity(medicineName, item.active_ingredient || "");
    const bestScore = Math.max(nameScore, ingScore);
    return { item, score: Math.round(bestScore * 100) / 100 };
  });

  scored.sort((a, b) => b.score - a.score);

  const topCandidates = scored.slice(0, 5).map((s) => ({
    id: s.item.id || s.item.product_id,
    name: s.item.name || s.item.product_name,
    activeIngredient: s.item.active_ingredient,
    score: s.score,
  }));

  const best = scored[0];

  // 3. Fail-closed threshold check:
  // If score >= threshold, return match.
  // CRITICAL FIX: If below threshold, DO NOT return catalog[0]! Return null!
  if (best && best.score >= threshold) {
    return {
      matchedProduct: best.item,
      similarity: best.score,
      candidates: topCandidates,
      requiresReview: false,
      matchType: "FUZZY",
    };
  }

  return {
    matchedProduct: null, // FAIL-CLOSED: No silent assumption
    similarity: best ? best.score : 0.0,
    candidates: topCandidates,
    requiresReview: true,
    reason: "BELOW_CONFIDENCE_THRESHOLD",
  };
}

module.exports = {
  findBestMedicineMatchSafe,
  normalizeText,
  calculateSimilarity,
};
