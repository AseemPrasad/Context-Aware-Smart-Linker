"""Synthetic test dataset generation for evaluation harness.

Generates realistic Q&A pairs from pre-computed domain samples.
No external API calls—uses local models or template-based generation.
"""

import os
import json
import random
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SyntheticExample:
    """A synthetic Q&A example for evaluation."""

    question_id: str
    question: str
    ground_truth_context: str
    expected_answer: str
    domain: str
    difficulty: str = "medium"  # easy, medium, hard


class DatasetGenerator:
    """Generate synthetic evaluation datasets from domain samples."""

    # Pre-computed domain samples (template-based, no API calls)
    DOMAIN_SAMPLES = {
        "python_docs": [
            {
                "question": "How to parse JSON in Python?",
                "context": "Use json.loads() for strings or json.load() for files",
                "answer": "Use json.loads() to parse JSON from a string",
            },
            {
                "question": "What is a list comprehension?",
                "context": "List comprehensions are a concise way to create lists using [expr for item in iterable]",
                "answer": "A concise syntax for creating lists by iterating over iterables",
            },
            {
                "question": "How to handle exceptions in Python?",
                "context": "Use try-except blocks to catch and handle exceptions",
                "answer": "Use try-except blocks to catch and handle exceptions",
            },
            {
                "question": "What is the purpose of __init__ in Python?",
                "context": "__init__ is the constructor method that initializes object attributes",
                "answer": "Constructor method that initializes object attributes",
            },
            {
                "question": "How to work with dictionaries?",
                "context": "Dictionaries store key-value pairs using curly braces: {key: value}",
                "answer": "Create dictionaries with curly braces and access values by keys",
            },
        ],
        "react_docs": [
            {
                "question": "What is React?",
                "context": "React is a JavaScript library for building user interfaces with components",
                "answer": "A JavaScript library for building interactive UIs with reusable components",
            },
            {
                "question": "How do hooks work in React?",
                "context": "Hooks are functions that let you 'hook into' React state and lifecycle features",
                "answer": "Functions that let you use React features in functional components",
            },
            {
                "question": "What is JSX?",
                "context": "JSX is a syntax extension that lets you write HTML-like code in JavaScript",
                "answer": "Syntax for writing HTML-like code directly in JavaScript",
            },
            {
                "question": "How does state management work?",
                "context": "State is managed using useState hook in functional components",
                "answer": "Use useState hook to manage component state in React",
            },
            {
                "question": "What is the purpose of useEffect?",
                "context": "useEffect runs side effects after rendering, replacing lifecycle methods",
                "answer": "Handles side effects in functional components",
            },
        ],
        "general_qa": [
            {
                "question": "What is machine learning?",
                "context": "Machine learning is a subset of AI that learns from data patterns",
                "answer": "A method of artificial intelligence that learns from data",
            },
            {
                "question": "How do neural networks work?",
                "context": "Neural networks use interconnected nodes to process information",
                "answer": "Systems inspired by biological neural networks that learn from examples",
            },
            {
                "question": "What is deep learning?",
                "context": "Deep learning uses multi-layer neural networks to extract features",
                "answer": "Neural networks with multiple layers for complex pattern recognition",
            },
            {
                "question": "What is natural language processing?",
                "context": "NLP is a field of AI that focuses on human language understanding",
                "answer": "Field of AI that enables computers to understand and process human language",
            },
            {
                "question": "What are transformers in NLP?",
                "context": "Transformers are neural network architectures that use attention mechanisms",
                "answer": "Deep learning models using attention to process sequential data",
            },
        ],
    }

    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)

    def generate_dataset(
        self, domain: str, size: int, include_variations: bool = True
    ) -> List[SyntheticExample]:
        """Generate synthetic dataset for a domain.

        Args:
            domain: Domain name (python_docs, react_docs, general_qa)
            size: Number of examples to generate
            include_variations: Whether to create question variations

        Returns:
            List of SyntheticExample objects
        """
        if domain not in self.DOMAIN_SAMPLES:
            logger.warning(f"Unknown domain: {domain}, using general_qa")
            domain = "general_qa"

        samples = self.DOMAIN_SAMPLES[domain]
        examples = []

        # Repeat and shuffle samples to reach desired size
        while len(examples) < size:
            shuffled = random.sample(samples, min(len(samples), size - len(examples)))

            for idx, sample in enumerate(shuffled):
                example = SyntheticExample(
                    question_id=f"{domain}_{len(examples)}",
                    question=sample["question"],
                    ground_truth_context=sample["context"],
                    expected_answer=sample["answer"],
                    domain=domain,
                    difficulty="medium",
                )
                examples.append(example)

                if len(examples) >= size:
                    break

        logger.info(f"Generated {len(examples)} examples for domain={domain}")
        return examples[:size]

    def save_dataset(self, examples: List[SyntheticExample], output_path: str) -> str:
        """Save generated dataset to JSON file.

        Args:
            examples: List of SyntheticExample objects
            output_path: Path to save JSON file

        Returns:
            Path to saved file
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        data = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "seed": self.seed,
                "num_examples": len(examples),
            },
            "examples": [
                {
                    "question_id": ex.question_id,
                    "question": ex.question,
                    "ground_truth_context": ex.ground_truth_context,
                    "expected_answer": ex.expected_answer,
                    "domain": ex.domain,
                    "difficulty": ex.difficulty,
                }
                for ex in examples
            ],
        }

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Dataset saved to {output_path}")
        return output_path

    @staticmethod
    def load_dataset(dataset_path: str) -> List[SyntheticExample]:
        """Load dataset from JSON file.

        Args:
            dataset_path: Path to JSON dataset file

        Returns:
            List of SyntheticExample objects
        """
        with open(dataset_path, "r") as f:
            data = json.load(f)

        examples = [
            SyntheticExample(
                question_id=ex["question_id"],
                question=ex["question"],
                ground_truth_context=ex["ground_truth_context"],
                expected_answer=ex["expected_answer"],
                domain=ex["domain"],
                difficulty=ex.get("difficulty", "medium"),
            )
            for ex in data.get("examples", [])
        ]

        logger.info(f"Loaded {len(examples)} examples from {dataset_path}")
        return examples


def create_builtin_datasets(output_dir: str = "evals/datasets") -> Dict[str, str]:
    """Create built-in datasets if they don't exist.

    Args:
        output_dir: Directory to save datasets

    Returns:
        Dict mapping dataset name to file path
    """
    generator = DatasetGenerator()
    datasets = {}

    for domain, size in [("python_docs", 50), ("react_docs", 50), ("general_qa", 50)]:
        filename = f"{domain}_v1.json"
        filepath = os.path.join(output_dir, filename)

        if not os.path.exists(filepath):
            examples = generator.generate_dataset(domain, size)
            generator.save_dataset(examples, filepath)
            logger.info(f"Created builtin dataset: {filename}")

        datasets[domain] = filepath

    return datasets
