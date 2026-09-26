import sys
import os
import json
import subprocess

routes = [
    # 10 Different Routes in Bengaluru
    {"name": "Route 1 (Koramangala to Indiranagar)", "o": (12.9350, 77.6245), "d": (12.9784, 77.6408)},
    {"name": "Route 2 (Jayanagar to Malleshwaram)", "o": (12.9299, 77.5826), "d": (13.0031, 77.5643)},
    {"name": "Route 3 (Whitefield to Silk Board)", "o": (12.9698, 77.7499), "d": (12.9177, 77.6238)},
    {"name": "Route 4 (Hebbal to MG Road)", "o": (13.0354, 77.5988), "d": (12.9719, 77.6013)},
    {"name": "Route 5 (BTM Layout to HSR Layout)", "o": (12.9166, 77.6101), "d": (12.9121, 77.6446)},
    {"name": "Route 6 (Rajajinagar to Basavanagudi)", "o": (12.9881, 77.5549), "d": (12.9406, 77.5738)},
    {"name": "Route 7 (Yelahanka to Manyata Tech Park)", "o": (13.1007, 77.5963), "d": (13.0450, 77.6206)},
    {"name": "Route 8 (Bellandur to Marathahalli)", "o": (12.9304, 77.6784), "d": (12.9569, 77.7011)},
    {"name": "Route 9 (Banashankari to Electronic City)", "o": (12.9172, 77.5755), "d": (12.8399, 77.6770)},
    {"name": "Route 10 (Yeshwanthpur to Peenya)", "o": (13.0249, 77.5401), "d": (13.0285, 77.5197)},
]

with open("config.json", "r") as f:
    orig_config = json.load(f)

test_config = orig_config.copy()

for i, r in enumerate(routes):
    test_config["locations"]["origin"]["lat"] = r["o"][0]
    test_config["locations"]["origin"]["lon"] = r["o"][1]
    test_config["locations"]["origin"]["name"] = r["name"] + " (Origin)"
    
    test_config["locations"]["destination"]["lat"] = r["d"][0]
    test_config["locations"]["destination"]["lon"] = r["d"][1]
    test_config["locations"]["destination"]["name"] = r["name"] + " (Dest)"
    
    with open("config.json", "w") as f:
        json.dump(test_config, f)
        
    print(f"\n{'='*50}\n=== RUNNING E2E TEST: {r['name']} ===\n{'='*50}")
    subprocess.run([".venv/bin/python", "main.py", "--dry-run"])

# Restore original config
with open("config.json", "w") as f:
    json.dump(orig_config, f)
    
print("\nE2E Live Test Complete!")
