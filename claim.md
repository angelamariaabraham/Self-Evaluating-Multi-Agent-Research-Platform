# Main claim
Adversarial verification agents catch unsupported claims in LLM-generated
research reports that a span-match check alone misses.

# Evidence I need
- Planted-error detection: span-match only vs each agent vs full pipeline
- Faithfulness over repeated runs (noise floor)
- Negative controls (no source text, broken tool)

# Future scope (not claimed)
- Quality-gated retry loop
- Multimodal sources
- User-feedback calibration
- Domain fine-tuning
- Cross-domain testing