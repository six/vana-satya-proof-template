# Time thresholds (in milliseconds)
MIN_TIME_SPENT_MS = 2000          # Minimum time spent on a page (2 seconds)
MAX_TIME_SPENT_MS = 1800000       # Maximum time spent on a page (30 mins)

# Completeness
REQUIRED_FIELDS = {'url', 'timeSpent'}

# Authenticity thresholds
LONG_DURATION_THRESHOLD_MS = 300000  # 5 minutes (300,000 ms) without actions

# Scoring weights
MAX_AUTHENTICITY_SCORE = 100

# Labeling thresholds based on overall score
HIGH_AUTHENTICITY_THRESHOLD = 0.8
MODERATE_AUTHENTICITY_THRESHOLD = 0.3

# Sigmoid Function Parameters
X0 = 0.5  # Midpoint of the sigmoid curve
K = 5     # Steepness of the curve