import math
from typing import Dict

import math

EARLY_BONUS_MULTIPLIER = 3

def recalculate_evaluation_metrics(decrypted_data: dict) -> dict:
    encrypted_browsing_data_array = decrypted_data.get('browsingDataArray', [])
    
    url_count = len(encrypted_browsing_data_array)
    time_spent_list = []
    total_time_spent = 0  # In seconds
    
    for entry in encrypted_browsing_data_array:
        # Handle time spent
        time_spent_ms = entry.get('timeSpent', 0)
        time_spent_sec = time_spent_ms / 1000.0  # Convert milliseconds to seconds
        time_spent_sec_int = math.floor(time_spent_sec)  # Floor for consistency
        time_spent_list.append(time_spent_sec_int)
        total_time_spent += time_spent_sec_int
        
        
    # Calculate points: (URL count + total actions) * 10 + total time spent + total cookies
    points = math.floor((url_count + total_time_spent/60) * EARLY_BONUS_MULTIPLIER)
    calculated_metrics = {
        'url_count': url_count,
        'timeSpent': time_spent_list,
        'points': points
    }
    
    return calculated_metrics

def verify_evaluation_metrics(calculated_metrics: dict, given_metrics: dict) -> bool:
    calculated_points = calculated_metrics.get('points', 0)
    given_points = given_metrics.get('points', 0)
    points_match = (calculated_points == given_points)
    
    metrics_match = (
        calculated_metrics.get('url_count', 0) == given_metrics.get('url_count', 0) and
        calculated_metrics.get('timeSpent', []) == given_metrics.get('timeSpent', []) 
    )
    
    authenticity = 1.0 if points_match and metrics_match else 0.0
    return authenticity
