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

        # Protección contra datasets gigantes
        if len(df) > 100000:
            df = df.sample(100000, random_state=42)

        self.df = df

        self.numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        self.categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()

    def generate_summary(self) -> dict:

        summary = {
            "overall": {
                "rows": int(len(self.df)),
                "columns": int(len(self.df.columns)),
                "missing_cells": int(self.df.isna().sum().sum())
            }
        }

        if self.numeric_cols:

            numeric_df = self.df[self.numeric_cols]

            summary["numeric_stats"] = numeric_df.describe().to_dict()

        if self.categorical_cols:

            cat_stats = {}

            for col in self.categorical_cols:

                try:

                    cat_stats[col] = {
                        "unique": int(self.df[col].nunique()),
                        "top": self.df[col].value_counts().head(1).to_dict()
                    }

                except Exception:
                    continue

            summary["categorical_stats"] = cat_stats

        return summary

    def detect_outliers(self) -> list:

        patterns = []

        if len(self.numeric_cols) < 2:
            return patterns

        try:

            X = self.df[self.numeric_cols].copy()

            X = X.fillna(X.mean())
            X = X.fillna(0)

            iso = IsolationForest(
                contamination="auto",
                random_state=42
            )

            preds = iso.fit_predict(X)

            outlier_indices = np.where(preds == -1)[0].tolist()

            if len(outlier_indices) > 0:

                patterns.append({
                    "type": "outliers",
                    "description": f"Detected {len(outlier_indices)} outliers",
                    "indices": outlier_indices[:10],
                    "confidence": 0.85,
                    "details": {
                        "method": "IsolationForest"
                    }
                })

        except Exception:
            pass

        return patterns

    def detect_clusters(self) -> list:

        patterns = []

        if len(self.numeric_cols) < 2 or len(self.df) < 10:
            return patterns

        try:

            X = self.df[self.numeric_cols].copy()

            X = X.fillna(X.mean())
            X = X.fillna(0)

            scaler = StandardScaler()

            X_scaled = scaler.fit_transform(X)

            best_k = 2
            best_score = -1

            max_k = min(6, max(2, len(self.df) // 5))

            for k in range(2, max_k + 1):

                km = KMeans(
                    n_clusters=k,
                    random_state=42,
                    n_init=10
                )

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
                    "details": {
                        "n_clusters": int(best_k),
                        "silhouette_score": float(best_score)
                    }
                })

        except Exception:
            pass

        return patterns

    def generate_recommendations(self) -> list:

        recs = []

        try:

            missing_pct = (self.df.isna().sum() / len(self.df)) * 100

            high_missing = missing_pct[missing_pct > 20]

            for col, pct in high_missing.items():

                recs.append({
                    "priority": "high",
                    "category": "data_quality",
                    "message": f"Column '{col}' has {pct:.1f}% missing values",
                    "action": "Consider imputing or dropping"
                })

        except Exception:
            pass

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
