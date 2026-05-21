# ML Services

This area should contain the scoring logic that makes Rayzaa technically credible.

## Recommended Modules

- `fraud_score.py`: anomaly or classification model
- `graph_score.py`: ring-risk heuristics
- `drift_score.py`: account drift logic
- `fusion.py`: final risk combination
- `explain.py`: SHAP outputs and analyst brief assembly

## Modeling Guidance

Use the minimum number of real models needed to make the system believable.

### Strong default path

- fraud score: XGBoost, LightGBM, or Isolation Forest
- graph score: NetworkX-based heuristics
- drift score: rules or small classifier
- explanation: SHAP + LLM summary

### Optional path if time remains

- small autoencoder on normalized transaction features

## Do Not Spend the Sprint On

- training a full GNN
- tuning multiple deep models in parallel
- large feature-store abstractions
- production retraining pipelines
