import my_proof.utils.constants as constants

def label_browsing_behavior(overall_score):
    """
    Labels the browsing behavior based on the overall score.
    """
    if overall_score >= constants.HIGH_AUTHENTICITY_THRESHOLD:
        return "High Authentic Browsing"
    elif overall_score >= constants.MODERATE_AUTHENTICITY_THRESHOLD:
        return "Moderate quality, Some traits of human browsing"
    else:
        return "Low quality, Potentially Non-Human Browsing"
