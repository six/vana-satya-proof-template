import json
import logging
import os
from typing import Dict, Any
from eth_account import Account
from eth_abi import encode
from eth_account.messages import encode_defunct
import base64
from my_proof.utils.decrypt import decryptData, verifyDataHash
from my_proof.models.proof_response import ProofResponse
from my_proof.utils.labeling import label_browsing_behavior
from my_proof.validation.evaluations import (
    evaluate_correctness,
    evaluate_quality,
    sigmoid,
)
from my_proof.validation.metrics import recalculate_evaluation_metrics, verify_evaluation_metrics
import my_proof.utils.constants as constants


class Proof:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def generate(self) -> ProofResponse:
        """Generate the proof response based on the input data."""
        logging.info("Starting proof generation")
        # Load and decrypt the input data
        input_data = self.load_input_data()
        # Create the proof response
        proof_response = self.create_proof_response(input_data)

        return proof_response

    def load_input_data(self) -> Dict[str, Any]:
        """Load the input data from a JSON file in the input directory."""
        input_dir = self.config['input_dir']
        json_files = [
            f for f in os.listdir(input_dir) if f.lower().endswith('.zip')
        ]
        if not json_files:
            raise FileNotFoundError("No JSON input files found in the input directory.")
        if len(json_files) > 1:
            logging.warning("Multiple JSON input files found. Using the first one.")
        input_file = os.path.join(input_dir, json_files[0])
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        return input_data

    def create_proof_response(
        self, input_data: Dict[str, Any]
    ) -> ProofResponse:
        """Create and populate the ProofResponse object."""
        proof_response = ProofResponse(dlp_id=self.config['dlp_id'])
        # Verify ownership
        ownership = self.verify_ownership(
            author=input_data.get('author'),
            signature=self.config.get("signed_message"),
            random_string=input_data.get('random_string'),
        )
        #Verify user honesty 
        given_metrics = input_data.get('data', {}).get('evaluationMetrics', {})
        recalculated_metrics = recalculate_evaluation_metrics(input_data.get('data', {}))
        authenticity = verify_evaluation_metrics(recalculated_metrics, given_metrics)
        integrity = verifyDataHash(input_data.get('data', {}),input_data['data_hash'])
       # Evaluate browsing data
        evaluation_result = self.evaluate_browsing_data(input_data.get('data', {}))
        correctness = evaluation_result['correctness']        # Raw correctness score
        quality = evaluation_result['quality_score']  # Raw quality score
        final_score = evaluation_result['final_score']
        label = evaluation_result['label']
        valid = ownership and authenticity and integrity and correctness and (final_score >= constants.MODERATE_AUTHENTICITY_THRESHOLD)

        # populate values
        proof_response.ownership = ownership
        proof_response.authenticity = authenticity
        proof_response.integrity = integrity
        proof_response.correctness = correctness
        proof_response.quality = quality
        proof_response.attributes = {
            'label': label,
        }
        proof_response.score = final_score  
        proof_response.valid = valid
        proof_response.metadata = {
            'dlp_id': self.config['dlp_id'],
            'valid': valid,
            'quality': quality
        }

        return proof_response
    
    
    def verify_ownership(
        self, author: str, signature: str, random_string: str
    ) -> float:
        """Verify the ownership of the data."""
        # Step 0: Validate Input Fields
        missing_fields = [
            field_name for field_name, value in {
                'author': author,
                'signature': signature,
                'random_string': random_string
            }.items() if not value
        ]
        if missing_fields:
            logging.error(f"Missing ownership verification data: {', '.join(missing_fields)}")
            return 0.0

        # Step 1: Encode the Message as Defunct (Treat as Text)
        try:
            # Since the client signs the hex string, treat random_string as text
            message_encoded = encode_defunct(text=random_string)
        except Exception as e:
            logging.error(f"Failed to encode message: {e}")
            return 0.0

        # Step 2: Recover the Signer's Address from the Signature
        try:
            recovered_address = Account.recover_message(message_encoded, signature=signature)
            # Compare the recovered address with the provided author address (case-insensitive)
            is_valid = 1.0 if recovered_address.lower() == author.lower() else 0.0
            if is_valid:
                logging.info(f"Ownership verified successfully for address: {recovered_address}")
            else:
                logging.warning(f"Recovered address {recovered_address} does not match author {author}")
            return is_valid
        except Exception as e:
            logging.error(f"Ownership verification failed: {e}")
            return 0.0
    

    def evaluate_browsing_data(self, browsing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate the browsing data for correctness and quality."""
        data_array = browsing_data.get("browsingDataArray", [])
        correctness = evaluate_correctness(data_array)
        quality = evaluate_quality(data_array)
        sigmoid_score = sigmoid(quality)
        label = label_browsing_behavior(sigmoid_score)

        return {
            'correctness': correctness,
            'quality_score': round(quality, 2),
            'final_score': round(sigmoid_score, 2), 
            'label': label,
        }

    # Placeholder for uniqueness evaluation
    def evaluate_uniqueness(self) -> int:
        pass
