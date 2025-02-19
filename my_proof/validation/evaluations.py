import my_proof.utils.constants as constants
from my_proof.utils.defs import is_valid_url
import statistics
import math

def sigmoid(x, k=constants.K, x0=constants.X0):
    """
    Applies the sigmoid function to the normalized score.
    Parameters:
        - x: Normalized input score (0..1).
        - k: Steepness of the curve.
        - x0: Midpoint of the sigmoid curve.
    """
    z = k * (x - x0)
    return 1 / (1 + math.exp(-z))

def evaluate_correctness(browsing_data):
    """
    Evaluates the 'correctness' of the browsing data under the new format.
    Only checks whether the provided dataArray follows the expected schema
    (i.e., each entry has 'url' and 'timeSpent', both valid).
    """
    correctness = False

    total_entries = len(browsing_data)
    completeness_issues = 0

    for entry in browsing_data:
        # Must contain both 'url' and 'timeSpent' keys
        if not constants.REQUIRED_FIELDS.issubset(entry.keys()):
            completeness_issues += 1
            continue
        # Validate URL
        url = entry['url']
        if not is_valid_url(url):
            completeness_issues += 1
            continue

    if total_entries == 0:
        return False  # No data => not correct

    # Example threshold:
    # "correct" if at least half of the entries are complete & valid
    correctness = (total_entries - completeness_issues) >= (total_entries / 2)
    return correctness

def parse_domain_and_path(url):
    """
    Parses a URL into (domain, path).
    Example:
      https://en.wikipedia.org/wiki/University_of_California
        -> domain = "en.wikipedia.org"
        -> path   = "/wiki/University_of_California"
    """
    stripped = url.replace("https://", "").replace("http://", "")
    parts = stripped.split("/", 1)  # split into at most 2 parts
    domain = parts[0]
    path = "/" + parts[1] if len(parts) > 1 else "/"
    return domain, path

def get_base_path(path):
    """
    A simplified approach to get the 'base path':
      e.g. "/wiki/University_of_California" -> "/wiki"
    """
    tokens = path.strip("/").split("/")
    if len(tokens) == 0 or not tokens[0]:
        return "/"  # no sub-path
    return f"/{tokens[0]}"

def evaluate_quality(browsing_data):
    """
    Evaluates the session using three "quotas":
      1) Navigation Path (weight=20)
      2) Time Duration (weight=50)
      3) Bot-Like Behavior (weight=30)
    
    Returns a final score in [0..1].
    """

    total_entries = len(browsing_data)
    if total_entries == 0:
        return 0.0

    # -----------------------------
    # A. Extract Basic Session Data
    # -----------------------------
    short_visits = 0
    long_visits = 0
    time_spent_values = []

    # For domain continuity checks
    no_continuity_count = 0
    sub_path_continuity_count = 0

    previous_domain = None
    previous_base_path = None

    # We'll also track all domain+path for advanced checks
    session_domain_paths = []

    # Collect data
    for entry in browsing_data:
        time_spent = entry.get('timeSpent', 0)
        url = entry.get('url', '')

        # short/long visits
        if time_spent < constants.MIN_TIME_SPENT_MS:
            short_visits += 1
        if time_spent > constants.LONG_DURATION_THRESHOLD_MS:
            long_visits += 1

        time_spent_values.append(time_spent)

        # Domain+path continuity
        if url and is_valid_url(url):
            domain, path = parse_domain_and_path(url)
            base_path = get_base_path(path)
            session_domain_paths.append((domain, base_path))

            if previous_domain and domain != previous_domain:
                no_continuity_count += 1
            else:
                # same domain => check sub-path continuity
                if (previous_base_path and base_path == previous_base_path
                        and domain == previous_domain):
                    sub_path_continuity_count += 1

            previous_domain = domain
            previous_base_path = base_path
        else:
            # invalid or missing => just store a placeholder
            session_domain_paths.append((None, None))

    # --------------
    # B. NAVIGATION (will be omitted for this version, not enough data point)
    # --------------
    
    # ---------------
    # C. TIME DURATION
    # ---------------
    #   Quota Weight = 50
    time_duration_quota_score = 1.0

    # (C1) Ratio of short visits
    short_visit_ratio = short_visits / total_entries
    # If > 75% are short => big penalty
    if short_visit_ratio > 0.75:
        # drastically reduce, e.g. set it to 0.2 or subtract 0.8
        time_duration_quota_score -= 0.8
    else:
        # smaller penalty scale based on ratio
        time_duration_quota_score -= (0.5 * short_visit_ratio)

    # (C2) Ratio of long visits
    long_visit_ratio = long_visits / total_entries
    # modest penalty
    time_duration_quota_score -= (0.3 * long_visit_ratio)

    # (C3) Extreme average
    import statistics
    mean_time = statistics.mean(time_spent_values)
    if mean_time < constants.MIN_TIME_SPENT_MS:
        time_duration_quota_score -= 0.3  # some penalty
    elif mean_time > constants.LONG_DURATION_THRESHOLD_MS:
        time_duration_quota_score -= 0.3

    # clamp time_duration_quota_score
    time_duration_quota_score = max(min(time_duration_quota_score, 1.0), 0.0)

    # -----------------------
    # D. BOT-LIKE BEHAVIOR
    # -----------------------
    #   Quota Weight = 30
    bot_like_quota_score = 1.0

    # (D1) Very similar timeSpent => suspicious
    # Let's define "very similar" = difference < 300ms
    # We'll check consecutive visits (or all pairs) for repeated or near-repeated times.
    similar_count = 0
    for i in range(total_entries - 1):
        if abs(time_spent_values[i] - time_spent_values[i+1]) < 300:  # 0.3s
            similar_count += 1
    if total_entries > 1:
        similar_ratio = similar_count / (total_entries - 1)
        # The higher the ratio, the bigger the penalty
        bot_like_quota_score -= 0.5 * similar_ratio

    # (D2) Sliding window check for repeated low timeSpent
    # If we find multiple consecutive low visits (e.g. 3 in a row),
    # that's suspicious. Let's define a small function to find consecutive blocks.
    def count_consecutive_low(arr, threshold=constants.MIN_TIME_SPENT_MS, block_size=3):
        consecutive_block_count = 0
        current_count = 0
        for val in arr:
            if val < threshold:
                current_count += 1
            else:
                # end block
                if current_count >= block_size:
                    consecutive_block_count += 1
                current_count = 0
        # check if ended with a block
        if current_count >= block_size:
            consecutive_block_count += 1
        return consecutive_block_count

    consecutive_low_blocks = count_consecutive_low(time_spent_values, block_size=3)
    # for each found block, penalize
    if consecutive_low_blocks > 0:
        # e.g. subtract up to 0.5 for each block, but not below 0
        penalty = 0.3 * consecutive_low_blocks
        bot_like_quota_score -= penalty

    # clamp
    bot_like_quota_score = max(min(bot_like_quota_score, 1.0), 0.0)

    # -----------------------------
    # E. Combine Using Quota Weights
    # -----------------------------
    # We have 3 partial scores in [0..1].
    # We multiply each by its quota weight, sum them, clamp to [0..100], then /100.
    TIME_WEIGHT = 60
    BOT_WEIGHT = 40

    time_component = time_duration_quota_score * TIME_WEIGHT
    bot_component = bot_like_quota_score * BOT_WEIGHT
    
    print("time_component: ",time_component, "bot_component: ",bot_component)

    final_raw = time_component + bot_component  # should be in [0..100] theoretically
    final_clamped = max(min(final_raw, 100), 0)
    final_score = final_clamped / 100.0

    return final_score
