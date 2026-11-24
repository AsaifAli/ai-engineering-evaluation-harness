# Project-specific replay evaluation

The active evaluator supports the two connected agency applications only:

- **EvidenceFlow** uses the `rag` pack.
- **QuoteSense** uses the `document_intelligence` pack.

Evaluation runs use small, synthetic, version-controlled fixtures. They are deterministic reference checks, not live model benchmarks, production accuracy claims or client outcome measurements.

## EvidenceFlow: retrieval and evidence quality

Metrics include Recall@K, Precision@K, MRR, MAP@K, nDCG@K, citation completeness/correctness, answer relevance and groundedness. These measure whether the retrieval ranking contains the expected evidence and whether the cited evidence supports the answer.

## QuoteSense: document and decision quality

Metrics include field exact match, critical-field accuracy, schema validity, numeric accuracy, risk classification F1 and recommendation consistency. This separates extraction correctness from deterministic schema/business-rule validation and higher-level recommendation quality.

## Run the fixtures

```bash
PYTHONPATH=. python -m evals.project_runner --target all --mode replay
```

Or run one retained application:

```bash
PYTHONPATH=. python -m evals.project_runner --target evidenceflow --mode replay
PYTHONPATH=. python -m evals.project_runner --target quotesense --mode replay
```

Results are stored by batch and exposed through `GET /api/ai-quality`. The public API filters historical rows to the two current public references, including when upgrading a database that contains old platform history.
