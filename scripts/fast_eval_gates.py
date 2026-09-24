"""Fast Multi-threaded Release Gate Verification.
Evaluates:
- Pure Routine (388 cases): Specificity >= 95%, Over-triage <= 5%, Routine -> Emergency <= 5%
- Pure T4 (989 cases): Pure T4 -> ROUTINE = 0, Pure T4 -> URGENT = 0, Sensitivity = 100%
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_1800_regression import load_all_1800_cases, evaluate_single_case

def main():
    cases = load_all_1800_cases()
    pure_t4 = [c for c in cases if c.expected_triage == "EMERGENCY" and (not c.acceptable_triages or c.acceptable_triages == ["EMERGENCY"])]
    pure_routine = [c for c in cases if c.expected_triage == "ROUTINE" and (not c.acceptable_triages or c.acceptable_triages == ["ROUTINE"])]

    print(f"Loaded: Total={len(cases)}, Pure T4={len(pure_t4)}, Pure Routine={len(pure_routine)}")

    run_salt = str(int(time.time()))

    # 1. Evaluate Pure Routine
    print("\nEvaluating 388 Pure Routine Cases with 8 workers...")
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as ex:
        routine_results = list(ex.map(lambda c: evaluate_single_case(c, run_salt), pure_routine))
    elapsed_rot = time.perf_counter() - t0

    rot_correct = sum(1 for r in routine_results if r["actual_triage"] == "ROUTINE")
    rot_urgent = sum(1 for r in routine_results if r["actual_triage"] == "URGENT")
    rot_emergency = sum(1 for r in routine_results if r["actual_triage"] == "EMERGENCY")
    rot_over = rot_urgent + rot_emergency
    rot_spec = rot_correct / len(pure_routine)

    print(f"  Done in {elapsed_rot:.1f}s")
    print(f"  Routine Benign Specificity: {rot_correct}/{len(pure_routine)} ({rot_spec*100:.2f}%)")
    print(f"  Routine Over-Triage:       {rot_over}/{len(pure_routine)} ({rot_over/len(pure_routine)*100:.2f}%)")
    print(f"  Routine -> URGENT:         {rot_urgent}")
    print(f"  Routine -> EMERGENCY:      {rot_emergency}")

    # 2. Evaluate Pure T4
    print("\nEvaluating 989 Pure T4 Cases with 8 workers...")
    t1 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as ex:
        t4_results = list(ex.map(lambda c: evaluate_single_case(c, run_salt), pure_t4))
    elapsed_t4 = time.perf_counter() - t1

    t4_emergency = sum(1 for r in t4_results if r["actual_triage"] == "EMERGENCY")
    t4_urgent = sum(1 for r in t4_results if r["actual_triage"] == "URGENT")
    t4_routine = sum(1 for r in t4_results if r["actual_triage"] == "ROUTINE")
    t4_sens = t4_emergency / len(pure_t4)

    print(f"  Done in {elapsed_t4:.1f}s")
    print(f"  Pure T4 Sensitivity:       {t4_emergency}/{len(pure_t4)} ({t4_sens*100:.2f}%)")
    print(f"  Pure T4 -> ROUTINE:        {t4_routine} (Gate: 0)")
    print(f"  Pure T4 -> URGENT:         {t4_urgent} (Gate: 0)")

    print("\n" + "=" * 80)
    print("GATE VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"Routine Benign Specificity >= 95%: {'PASS' if rot_spec >= 0.95 else 'FAIL'} ({rot_spec*100:.2f}%)")
    print(f"Routine Benign Over-Triage <= 5%:  {'PASS' if rot_over/len(pure_routine) <= 0.05 else 'FAIL'} ({rot_over/len(pure_routine)*100:.2f}%)")
    print(f"Routine -> Emergency <= 5%:       {'PASS' if rot_emergency/len(pure_routine) <= 0.05 else 'FAIL'} ({rot_emergency/len(pure_routine)*100:.2f}%)")
    print(f"Pure T4 -> ROUTINE == 0:          {'PASS' if t4_routine == 0 else 'FAIL'} ({t4_routine} cases)")
    print(f"Pure T4 -> URGENT == 0:           {'PASS' if t4_urgent == 0 else 'FAIL'} ({t4_urgent} cases)")
    print(f"Pure T4 Sensitivity == 100%:      {'PASS' if t4_sens == 1.0 else 'FAIL'} ({t4_sens*100:.2f}%)")
    print("=" * 80)

if __name__ == "__main__":
    main()
