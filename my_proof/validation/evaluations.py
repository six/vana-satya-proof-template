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
      https://en.wikipedia.org/wiki/University_of_California,_Berkeley
      -> domain="en.wikipedia.org", path="/wiki/University_of_California,_Berkeley"
    """
    # Remove protocol (if any)
    stripped = url.replace("https://", "").replace("http://", "")
    # Split on the first slash
    parts = stripped.split("/", 1)  # maxsplit=1
    domain = parts[0]
    path = "/" + parts[1] if len(parts) > 1 else "/"
    return domain, path

def get_base_path(path):
    """
    A simple heuristic to identify the 'base path' (e.g., "/wiki" from "/wiki/University_of_California").
    We'll assume the base path is everything up to the second slash or the end if none.
    
    Example:
      path="/wiki/University_of_California,_Berkeley" -> "/wiki"
      path="/blog/article/new" -> "/blog"
      path="/" -> "/"
    """
    # If there's only one slash, path is "/something" or just "/"
    # We split by '/' ignoring the leading one:
    tokens = path.strip("/").split("/")
    if len(tokens) == 0 or tokens[0] == '':
        return "/"  # no real sub-path
    # Return the first token with a leading slash
    return f"/{tokens[0]}"

def evaluate_authenticity(browsing_data):
    """
    Evaluates how 'human-like' the session is with the new structure:
    [
      {"url": <string>, "timeSpent": <int>},
      ...
    ]

    Key heuristics:
      - Short visit ratio
      - Long visit ratio
      - Domain + sub-path continuity
        * Reward staying on same domain/base-path across consecutive visits
      - Any sliding window of N (e.g. 5) visits:
        * If all domains differ => domain-hopping => suspicious
        * If all are extremely low timeSpent => suspicious
      - Session timing patterns (avg & stdev of timeSpent)
      - Session segmentation by domain => check total timeSpent per domain
    """

    authenticity_score = constants.MAX_AUTHENTICITY_SCORE  # e.g. 100
    total_entries = len(browsing_data)

    if total_entries == 0:
        return 0.0  # No data => cannot judge authenticity

    short_visits = 0
    long_visits = 0

    # For domain continuity checks
    no_continuity_count = 0     # how many consecutive domain changes?
    # For sub-path continuity (reward consecutive visits in the same base path)
    sub_path_continuity_count = 0

    # We'll store domain + base_path for each entry
    session_domain_paths = []
    time_spent_values = []

    # --- 1) Basic iteration: short/long visits, domain continuity checks ---
    previous_domain = None
    previous_base_path = None

    for entry in browsing_data:
        time_spent = entry.get('timeSpent', 0)
        url = entry.get('url', '')

        # (a) short/long visits
        if time_spent < constants.MIN_TIME_SPENT_MS:
            short_visits += 1
        if time_spent > constants.LONG_DURATION_THRESHOLD_MS:
            long_visits += 1

        time_spent_values.append(time_spent)

        # (b) domain & path continuity
        if url and is_valid_url(url):
            domain, path = parse_domain_and_path(url)
            base_path = get_base_path(path)
            session_domain_paths.append((domain, base_path))

            if previous_domain and domain != previous_domain:
                no_continuity_count += 1
            else:
                # same domain => check if base path is also the same
                if previous_base_path and base_path == previous_base_path and domain == previous_domain:
                    # Consecutive visits in same domain & same base path => 
                    # user might be browsing within "wiki" or "blog" sub-path.
                    sub_path_continuity_count += 1

            previous_domain = domain
            previous_base_path = base_path
        else:
            # If invalid or missing, do nothing special
            session_domain_paths.append((None, None))

    # ------------------------
    # (A) Short visit penalty
    # ------------------------
    short_visit_ratio = short_visits / total_entries
    authenticity_score -= (short_visit_ratio * 20)

    # ------------------------
    # (B) Long visit penalty
    # ------------------------
    long_visit_ratio = long_visits / total_entries
    authenticity_score -= (long_visit_ratio * 15)

    # -------------------------------------------------
    # (C) Domain continuity / sub-path continuity bonus
    # -------------------------------------------------
    # If user frequently remains on the same domain, continuity_ratio > 0
    if total_entries > 1:
        max_possible_changes = total_entries - 1
        continuity_ratio = 1 - (no_continuity_count / max_possible_changes)
        # If continuity_ratio is 0 => changed domain on *every* visit => suspicious
        if continuity_ratio == 0:
            authenticity_score -= 10
        else:
            # Higher domain continuity => slight reward
            authenticity_score += continuity_ratio * 5

    # Additional small reward for sub-path continuity
    # e.g., if user visits 10 consecutive pages in same base path => sub_path_continuity_count=9 for those transitions
    if total_entries > 1:
        sub_path_ratio = sub_path_continuity_count / (total_entries - 1)
        # Reward it a bit more heavily if you want:
        authenticity_score += (sub_path_ratio * 5)

    # -----------------------------------------
    # (D) SLIDING WINDOW of size N (e.g., 5)
    #     - Domain correlation
    #     - All extremely low timeSpent
    # -----------------------------------------
    N = 3
    # We'll examine all consecutive windows of size 5 (or up to total_entries if <5).
    # For each window:
    #   (1) if all distinct domains => penalty
    #   (2) if all timeSpent < MIN_TIME_SPENT_MS => penalty
    for start_idx in range(total_entries - N + 1):
        window = browsing_data[start_idx : start_idx + N]
        # Domains in the window
        dset = set()
        # TimeSpent in the window
        w_times = []

        for entry in window:
            url = entry.get('url', '')
            time_spent = entry.get('timeSpent', 0)
            if url and is_valid_url(url):
                d, _ = parse_domain_and_path(url)
                dset.add(d)
            w_times.append(time_spent)

        # (D1) Domain correlation check
        # If the window has 5 distinct domains => suspicious domain-hopping
        if len(dset) == N:
            authenticity_score -= 8  # or -10, your call

        # (D2) Common pattern of extremely low timeSpent
        # If *all* timeSpent in that window < MIN_TIME_SPENT_MS => suspicious
        if all(ts < constants.MIN_TIME_SPENT_MS for ts in w_times):
            authenticity_score -= 8

    # --------------------------------
    # (E) Session timing pattern check
    # --------------------------------
    mean_time = statistics.mean(time_spent_values)
    stdev_time = statistics.pstdev(time_spent_values) if len(time_spent_values) > 1 else 0

    # (E1) Extreme average penalty
    if mean_time < constants.MIN_TIME_SPENT_MS:
        authenticity_score -= 10
    if mean_time > constants.LONG_DURATION_THRESHOLD_MS:
        authenticity_score -= 10

    # (E2) Suspiciously low std dev => uniform times => penalize
    if mean_time > 0:
        stdev_ratio = stdev_time / mean_time
        if stdev_ratio < 0.1:
            authenticity_score -= 5

    # -----------------------------------
    # (F) Session Segmentation by Domain
    # -----------------------------------
    # Group consecutive visits to the same domain => "sections"
    domain_sections = []
    if total_entries > 0:
        current_domain = None
        current_time_spent = 0

        for entry in browsing_data:
            url = entry.get('url', '')
            ts = entry.get('timeSpent', 0)
            if url and is_valid_url(url):
                d, _ = parse_domain_and_path(url)
                if d != current_domain:
                    # store the previous segment if any
                    if current_domain is not None:
                        domain_sections.append({
                            "domain": current_domain,
                            "time_spent": current_time_spent
                        })
                    current_domain = d
                    current_time_spent = ts
                else:
                    current_time_spent += ts
            else:
                # invalid or missing domain
                pass

        # store the last open segment
        if current_domain is not None:
            domain_sections.append({
                "domain": current_domain,
                "time_spent": current_time_spent
            })

    # If multiple sections exist but *all* have the exact same timeSpent => suspicious
    if len(domain_sections) > 1:
        times = [section["time_spent"] for section in domain_sections]
        if len(set(times)) == 1:
            authenticity_score -= 10

    # Ensure final is in [0..MAX_AUTHENTICITY_SCORE]
    authenticity_score = max(min(authenticity_score, constants.MAX_AUTHENTICITY_SCORE), 0)
    print("authenticity_score:",authenticity_score)
    # Normalize to [0..1]
    return authenticity_score / 100
