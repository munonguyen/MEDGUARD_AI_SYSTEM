"""4-Stage Prescription Vision OCR Pipeline Package.

Stage 1: Preprocessing & Text Region Detection (PaddleOCR-det / region segmentation)
Stage 2: Vietnamese Line Recognition (VietOCR)
Stage 3: Structured Clinical Entity Normalization (Vintern-1B / VLM + JSON schema)
Stage 4: Fail-Closed Catalog Matching (Similarity >= 0.85, null on mismatch)
"""
