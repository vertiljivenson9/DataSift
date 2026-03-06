import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class EnhancedDataAnalyzer:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        self.categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    def generate_summary(self) -> dict:
        summary = {
            "overall": {
                "rows": len(self.df),
                "columns": len(self.df.columns),
                "missing_cells": int(self.df.isna().sum().sum())
            }
        }
        if self.numeric_cols:
            summary["numeric_stats"] = self.df[self.numeric_cols].describe().to_dict()
        if self.categorical_cols:
            cat_stats = {}
            for col in self.categorical_cols:
                cat_stats[col] = {
                    "unique": int(self.df[col].nunique()),
                    "top": self.df[col].value_counts().head(1).to_dict()
                }
            summary["categorical_stats"] = cat_stats
        return summary

    def detect_outliers(self) -> list:
        patterns = []
        if len(self.numeric_cols) < 2:
            return patterns
        X = self.df[self.numeric_cols].fillna(self.df[self.numeric_cols].mean())
        iso = IsolationForest(contamination=0.1, random_state=42)
        preds = iso.fit_predict(X)
        outlier_indices = np.where(preds == -1)[0].tolist()
        if outlier_indices:
            patterns.append({
                "type": "outliers",
                "description": f"Detected {len(outlier_indices)} outliers",
                "indices": outlier_indices[:10],
                "confidence": 0.85,
                "details": {"method": "Isolation Forest"}
            })
        return patterns

    def detect_clusters(self) -> list:
        patterns = []
        if len(self.numeric_cols) < 2 or len(self.df) < 10:
            return patterns
        X = self.df[self.numeric_cols].fillna(self.df[self.numeric_cols].mean())
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        best_k = 2
        best_score = -1
        for k in range(2, min(6, len(self.df)//5 + 2)):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X_scaled)
            if len(set(labels)) > 1:
                score = silhouette_score(X_scaled, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
        if best_score > 0.3:
            patterns.append({
                "type": "clusters",
                "description": f"Found {best_k} clusters (silhouette: {best_score:.3f})",
                "indices": None,
                "confidence": float(best_score),
                "details": {"n_clusters": best_k, "silhouette_score": float(best_score)}
            })
        return patterns

    def generate_recommendations(self) -> list:
        recs = []
        missing_pct = (self.df.isna().sum() / len(self.df)) * 100
        high_missing = missing_pct[missing_pct > 20]
        for col, pct in high_missing.items():
            recs.append({
                "priority": "high",
                "category": "data_quality",
                "message": f"Column '{col}' has {pct:.1f}% missing values",
                "action": "Consider imputing or dropping"
            })
        if len(self.df) < 100:
            recs.append({
                "priority": "high",
                "category": "business",
                "message": "Dataset is small (<100 rows)",
                "action": "Collect more data for reliable analysis"
            })
        return recs

    def generate_complete_report(self, analysis_type: str = "full") -> dict:
        report = {
            "summary": self.generate_summary(),
            "patterns": [],
            "recommendations": self.generate_recommendations()
        }
        if analysis_type in ["full", "quick"]:
            report["patterns"].extend(self.detect_outliers())
            if analysis_type == "full":
                report["patterns"].extend(self.detect_clusters())
        return report
