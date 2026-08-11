"""Dataset management with train/test splitting and data leakage detection."""

import os
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DatasetMetadata:
    """Metadata for a dataset."""

    name: str
    version: str
    generated_at: str
    total_examples: int
    train_count: int
    test_count: int
    split_seed: int
    leakage_detected: bool = False
    leakage_details: str = ""
    last_used: str = ""


class DatasetManager:
    """Manages dataset loading, splitting, versioning, and audit logging."""

    def __init__(self, dataset_dir: str = "evals/datasets"):
        self.dataset_dir = dataset_dir
        os.makedirs(dataset_dir, exist_ok=True)
        self.metadata_index: Dict[str, DatasetMetadata] = {}
        self._load_metadata_index()

    def _load_metadata_index(self) -> None:
        """Load metadata index from disk if available."""
        index_path = os.path.join(self.dataset_dir, "metadata_index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, "r") as f:
                    data = json.load(f)
                    logger.info(f"Loaded metadata index with {len(data.get('datasets', {}))} datasets")
            except Exception as e:
                logger.warning(f"Failed to load metadata index: {e}")

    def _save_metadata_index(self) -> None:
        """Save metadata index to disk."""
        index_path = os.path.join(self.dataset_dir, "metadata_index.json")
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_datasets": len(self.metadata_index),
            "datasets": {
                name: {
                    "version": meta.version,
                    "total_examples": meta.total_examples,
                    "train_count": meta.train_count,
                    "test_count": meta.test_count,
                    "leakage_detected": meta.leakage_detected,
                }
                for name, meta in self.metadata_index.items()
            },
        }

        with open(index_path, "w") as f:
            json.dump(data, f, indent=2)

    def split_dataset(
        self,
        dataset_path: str,
        train_ratio: float = 0.8,
        seed: int = 42,
        detect_leakage: bool = True,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        """Split dataset into train and test sets with leakage detection.

        Args:
            dataset_path: Path to dataset JSON file
            train_ratio: Fraction for training (0.8 = 80/20 split)
            seed: Random seed for reproducibility
            detect_leakage: Whether to detect semantic duplicates

        Returns:
            Tuple of (train_data, test_data, leakage_warnings)
        """
        import random

        random.seed(seed)

        with open(dataset_path, "r") as f:
            data = json.load(f)

        examples = data.get("examples", [])
        random.shuffle(examples)

        split_idx = int(len(examples) * train_ratio)
        train_examples = examples[:split_idx]
        test_examples = examples[split_idx:]

        warnings = []

        if detect_leakage:
            warnings = self._detect_leakage(train_examples, test_examples)

        train_data = {
            "metadata": {
                **data.get("metadata", {}),
                "split": "train",
                "count": len(train_examples),
                "split_seed": seed,
            },
            "examples": train_examples,
        }

        test_data = {
            "metadata": {
                **data.get("metadata", {}),
                "split": "test",
                "count": len(test_examples),
                "split_seed": seed,
                "leakage_detected": len(warnings) > 0,
            },
            "examples": test_examples,
        }

        logger.info(
            f"Split dataset: {len(train_examples)} train, {len(test_examples)} test "
            f"(warnings: {len(warnings)})"
        )

        return train_data, test_data, warnings

    def _detect_leakage(self, train_examples: List[dict], test_examples: List[dict]) -> List[str]:
        """Detect semantic duplicates between train and test sets.

        Args:
            train_examples: Training set examples
            test_examples: Test set examples

        Returns:
            List of leakage warnings
        """
        warnings = []

        # Simple word-overlap based detection (no embeddings required)
        for test_ex in test_examples:
            test_q = set(test_ex.get("question", "").lower().split())

            for train_ex in train_examples:
                train_q = set(train_ex.get("question", "").lower().split())

                # If >80% word overlap, consider it a duplicate
                if test_q and train_q:
                    overlap = len(test_q & train_q) / max(len(test_q), len(train_q))
                    if overlap > 0.8:
                        warnings.append(
                            f"Leakage detected: test question '{test_ex.get('question', '')[:40]}' "
                            f"overlaps with train (similarity: {overlap:.2f})"
                        )

        if warnings:
            logger.warning(f"Data leakage detected: {len(warnings)} potential duplicates")

        return warnings

    def save_split(
        self, train_data: Dict[str, Any], test_data: Dict[str, Any], dataset_name: str
    ) -> Tuple[str, str]:
        """Save train/test split to separate JSON files.

        Args:
            train_data: Training set data
            test_data: Test set data
            dataset_name: Base name for files (e.g., 'python_docs_v1')

        Returns:
            Tuple of (train_path, test_path)
        """
        train_path = os.path.join(self.dataset_dir, f"{dataset_name}_train.json")
        test_path = os.path.join(self.dataset_dir, f"{dataset_name}_test.json")

        with open(train_path, "w") as f:
            json.dump(train_data, f, indent=2)

        with open(test_path, "w") as f:
            json.dump(test_data, f, indent=2)

        logger.info(f"Saved train split: {train_path}")
        logger.info(f"Saved test split: {test_path}")

        return train_path, test_path

    def list_datasets(self) -> List[str]:
        """List all available datasets.

        Returns:
            List of dataset filenames
        """
        datasets = []
        for filename in os.listdir(self.dataset_dir):
            if filename.endswith(".json") and not filename.startswith("metadata"):
                datasets.append(filename)
        return sorted(datasets)

    def get_by_domain(self, domain: str) -> List[str]:
        """Get all datasets for a specific domain.

        Args:
            domain: Domain name (e.g., 'python_docs')

        Returns:
            List of matching dataset paths
        """
        matching = []
        for filename in self.list_datasets():
            if domain in filename and not filename.endswith("_train.json") and not filename.endswith("_test.json"):
                filepath = os.path.join(self.dataset_dir, filename)
                matching.append(filepath)
        return matching

    def get_latest_version(self, domain: str) -> Optional[str]:
        """Get path to latest version of a dataset.

        Args:
            domain: Domain name (e.g., 'python_docs')

        Returns:
            Path to latest dataset version, or None if not found
        """
        candidates = self.get_by_domain(domain)
        if candidates:
            # Sort by version (assuming naming like domain_v1.json, domain_v2.json)
            candidates.sort()
            return candidates[-1]  # Return last (highest version)
        return None

    def record_usage(self, dataset_path: str) -> None:
        """Record that a dataset was used (for audit trail).

        Args:
            dataset_path: Path to dataset that was used
        """
        filename = os.path.basename(dataset_path)
        if filename in self.metadata_index:
            self.metadata_index[filename].last_used = datetime.utcnow().isoformat()
            self._save_metadata_index()

        logger.info(f"Recorded usage for dataset: {filename}")

    def load_test_split(self, dataset_path: str) -> List[dict]:
        """Load test split for evaluation.

        Args:
            dataset_path: Path to dataset

        Returns:
            List of test examples
        """
        # Check if test split exists
        base = dataset_path.replace(".json", "").replace("_v1", "").replace("_v2", "").replace("_v3", "")
        test_path = f"{base}_test.json"

        if os.path.exists(test_path):
            with open(test_path, "r") as f:
                data = json.load(f)
                examples = data.get("examples", [])
                logger.info(f"Loaded test split: {len(examples)} examples from {test_path}")
                return examples

        # Fallback: load main file if no split exists
        if os.path.exists(dataset_path):
            with open(dataset_path, "r") as f:
                data = json.load(f)
                examples = data.get("examples", [])
                logger.info(f"No test split found, using main dataset: {len(examples)} examples")
                return examples

        logger.warning(f"Dataset not found: {dataset_path}")
        return []


def get_manager(dataset_dir: str = "evals/datasets") -> DatasetManager:
    """Get singleton dataset manager instance."""
    return DatasetManager(dataset_dir)
