"""
Centralized configuration for answer validation rules.
This prevents duplicating rules in every ExpectedAnswer object.
"""

ANSWER_VALIDATION_CONFIG = {
    'numeric': {
        'tolerance': 0.001,
        'strip_whitespace': True,
        'allowed_chars': '0-9.-',
    },
    'expression': {
        'simplify': True,
        'use_sympy': True,
    },
    'set': {
        'format': 'auto',           # próbuje rozpoznać przedział lub R \ {x}
        'allow_infinity': True,
        'normalize_whitespace': True,
    },
    'text': {
        'case_sensitive': False,
        'strip_whitespace': True,
    },
}


def get_validation_rules(answer_type: str, custom_rules: dict = None):
    """
    Returns default rules for given answer_type merged with custom rules.
    """
    defaults = ANSWER_VALIDATION_CONFIG.get(answer_type, {}).copy()
    
    if custom_rules:
        defaults.update(custom_rules)
    
    return defaults