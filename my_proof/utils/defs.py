import re

def extract_domain(url):
    """
    Extracts the domain from a given URL.
    """
    pattern = r'^(?:https?)://([^/?#]+)'
    match = re.match(pattern, url)
    return match.group(1).lower() if match else None


def is_valid_url(url):
    """
    Validates the URL format
    """
    regex = re.compile(
        r'^(?:https?)://'  # http://, https://
        r'(?:\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None
