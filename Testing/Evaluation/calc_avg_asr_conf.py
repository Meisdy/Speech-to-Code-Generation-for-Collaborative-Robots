log_file = "Logs/cobot_frontend.log"
confidences = []

with open(log_file, "r") as f:
    for line in f:
        if "confidence =" in line:
            confidence = float(line.split("confidence = ")[-1].strip())
            confidences.append(confidence)

avg = sum(confidences) / len(confidences)
min_conf = min(confidences)
max_conf = max(confidences)

print(f"Total ASR trials: {len(confidences)}")
print(f"Average confidence: {avg:.4f}")
print(f"Confidence range: [{min_conf:.2f}, {max_conf:.2f}]")
