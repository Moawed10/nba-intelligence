/** Display names for model-registry enums (backend app/models/registry.py). */
export const TARGET_LABELS: Record<string, string> = {
  pts: "Points",
  reb: "Rebounds",
  ast: "Assists",
  fg3m: "3-pointers made",
  stl: "Steals",
  blk: "Blocks",
  min: "Minutes",
  double_double: "Double-double",
};

export const TARGET_ORDER = ["pts", "reb", "ast", "fg3m", "stl", "blk", "min"] as const;

export const ALGORITHM_LABELS: Record<string, string> = {
  rolling_baseline: "Baseline (last 10 games)",
  ridge: "Ridge regression",
  random_forest: "Random forest",
  xgboost: "XGBoost",
  logistic: "Logistic regression",
  xgboost_classifier: "XGBoost classifier",
};

export const targetLabel = (target: string) => TARGET_LABELS[target] ?? target;
export const algorithmLabel = (algorithm: string) => ALGORITHM_LABELS[algorithm] ?? algorithm;
