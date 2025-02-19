from typing import Dict, Optional, Any

from pydantic import BaseModel


class ProofResponse(BaseModel):
    """
    Represents the response of a proof of contribution. Only the score and metadata will be written onchain, the rest of the proof lives offchain.

    Onchain attributes - these are written to the data registry:
        score: A score between 0 and 1 for the file, used to determine how valuable the file is. This can be an aggregation of the individual scores below.
        metadata: Additional metadata about the proof

    Offchain attributes - the remainder of the proof is written to IPFS
        dlp_id: The DLP ID is found in the DLP Root Network contract after the DLP is registered.
        valid: A single boolean to summarize if the file is considered valid in this DLP.
        integrity: A single boolean to verify if data was tampered or not
        authenticity: A score between 0 and 1 to verify the file was not falsy created or tampered with.
        quality: A score between 0 and 1 to rate if the file was a geniune human browsing or not.
        ownership: A score between 0 and 1 to verify the ownership of the file.
        correctness: A score between 0 and 1 to show the correctness of the file
        uniqueness: A score between 0 and 1 to show unique the file is, compared to others in the DLP.
        attributes: Custom attributes added to the proof to provide extra context about the encrypted file.
    """

    dlp_id: int
    valid: bool = False
    correctness: bool = False
    integrity: bool = False
    score: float = 0.0
    quality: float = 0.0
    ownership: float = 0.0
    authenticity: float = 0.0
    uniqueness: float = 0.0
    attributes: Optional[Dict[str, Any]] = {}
    metadata: Optional[Dict[str, Any]] = {}  # Human-readable metadata
