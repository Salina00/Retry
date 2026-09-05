import json
import os
import sys
import time
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.app.db import Base
from backend.app.models import Case, AuditLogEntry
from backend.app.pipeline.diagnosis import run_ai_diagnosis

def run_evaluation():
    # 1. Load eval set
    eval_file_path = os.path.join(os.path.dirname(__file__), "eval_set.json")
    with open(eval_file_path, "r") as f:
        eval_cases = json.load(f)

    print(f"Loaded {len(eval_cases)} evaluation cases.")

    # 2. Setup in-memory DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    correct_severity = 0
    correct_cause = 0
    provider_counts = {}
    results = []

    print("\nRunning diagnosis pipeline for evaluation...")
    for idx, tc in enumerate(eval_cases):
        code = tc["failure_code"]
        desc = tc["failure_description"]
        expected_cause = tc["expected_root_cause"]
        expected_severity = tc["expected_severity"]

        # Create dummy case
        case = Case(
            leak_type="payment_failure",
            status="detected",
            customer_reference=f"eval_customer_{idx}",
            amount=100.0,
            created_at=datetime.utcnow()
        )
        db.add(case)
        db.commit()

        # Run diagnosis with gentle interval
        time.sleep(1)
        diagnosis = run_ai_diagnosis(db, case.id, code, desc)

        audit = db.query(AuditLogEntry).filter(AuditLogEntry.case_id == case.id, AuditLogEntry.step == "diagnosis").first()
        provider = audit.source if audit else "unknown"
        provider_counts[provider] = provider_counts.get(provider, 0) + 1

        # Check
        severity_match = diagnosis.severity == expected_severity
        cause_match = diagnosis.root_cause == expected_cause

        if severity_match:
            correct_severity += 1
        if cause_match:
            correct_cause += 1

        results.append({
            "code": code,
            "provider": provider,
            "expected_cause": expected_cause,
            "got_cause": diagnosis.root_cause,
            "cause_match": cause_match,
            "expected_severity": expected_severity,
            "got_severity": diagnosis.severity,
            "severity_match": severity_match,
            "reasoning": diagnosis.reasoning
        })

    # Print results
    print("\n" + "="*80)
    print(" EVALUATION METRICS")
    print("="*80)
    
    total = len(eval_cases)
    severity_acc = (correct_severity / total) * 100
    cause_acc = (correct_cause / total) * 100

    print(f"Total Evaluated: {total}")
    print(f"Severity Accuracy:  {severity_acc:.1f}% ({correct_severity}/{total})")
    print(f"Root Cause Accuracy: {cause_acc:.1f}% ({correct_cause}/{total})")
    print("-" * 80)
    print("Provider Breakdown:")
    for prov, count in provider_counts.items():
        print(f"  - {prov}: {count}/{total}")
    print("-" * 80)
    
    print(f"{'Code':<38} | {'Provider':<16} | {'Expected':<16} | {'Got':<16} | {'S':<3} | {'C':<3}")
    print("-" * 80)
    for r in results:
        code_short = r["code"][:36]
        prov_short = r["provider"].replace("_diagnosis", "")[:14]
        s_ok = "YES" if r["severity_match"] else "NO"
        c_ok = "YES" if r["cause_match"] else "NO"
        print(f"{code_short:<38} | {prov_short:<16} | {r['expected_cause'][:16]:<16} | {r['got_cause'][:16]:<16} | {s_ok:<3} | {c_ok:<3}")
        
    print("="*80)
    
    # Write to log file
    try:
        with open("eval_run.log", "w") as lf:
            lf.write("="*80 + "\n")
            lf.write(" EVALUATION METRICS\n")
            lf.write("="*80 + "\n")
            lf.write(f"Total Evaluated: {total}\n")
            lf.write(f"Severity Accuracy:  {severity_acc:.1f}% ({correct_severity}/{total})\n")
            lf.write(f"Root Cause Accuracy: {cause_acc:.1f}% ({correct_cause}/{total})\n")
            lf.write("-" * 80 + "\n")
            lf.write(f"{'Code':<42} | {'Expected Cause':<22} | {'Got Cause':<22} | {'S_OK':<4} | {'C_OK':<4}\n")
            lf.write("-" * 80 + "\n")
            for r in results:
                code_short = r["code"][:40]
                s_ok = "YES" if r["severity_match"] else "NO"
                c_ok = "YES" if r["cause_match"] else "NO"
                lf.write(f"{code_short:<42} | {r['expected_cause']:<22} | {r['got_cause']:<22} | {s_ok:<4} | {c_ok:<4}\n")
            lf.write("="*80 + "\n")
    except Exception as e:
        print(f"Failed to write eval_run.log: {e}")
    
    # Write to json file for quick dashboard lookup
    try:
        results_file_path = os.path.join(os.path.dirname(__file__), "eval_results.json")
        with open(results_file_path, "w") as rf:
            json.dump({
                "severity_accuracy": severity_acc,
                "root_cause_accuracy": cause_acc,
                "total": total,
                "last_run": datetime.utcnow().isoformat()
            }, rf, indent=2)
    except Exception as e:
        print(f"Failed to write eval_results.json: {e}")
    
    db.close()
    
    return {
        "total": total,
        "severity_accuracy": severity_acc,
        "root_cause_accuracy": cause_acc
    }

if __name__ == "__main__":
    run_evaluation()
