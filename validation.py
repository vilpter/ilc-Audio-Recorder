#!/usr/bin/env python3
"""
Input Validation Utilities
Centralized validation functions for API inputs and user data
"""

import re
from typing import Optional, Tuple, Any


class ValidationError(ValueError):
    """Custom exception for validation errors"""
    pass


def validate_duration(duration: Any, allow_none: bool = False, allow_override: bool = False) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Validate recording duration parameter.

    Args:
        duration: Duration value to validate (can be any type)
        allow_none: If True, None is acceptable (for indefinite recordings)
        allow_override: If True, skip maximum duration check

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, duration_int: int|None)

    Examples:
        >>> validate_duration(3600)
        (True, None, 3600)
        >>> validate_duration(-100)
        (False, 'Duration must be positive', None)
        >>> validate_duration('abc')
        (False, 'Duration must be a number', None)
    """
    # Maximum duration: 4 hours (14400 seconds)
    MAX_DURATION = 14400

    # Check for None
    if duration is None:
        if allow_none:
            return True, None, None
        return False, "Duration is required", None

    # Type validation - must be numeric
    if not isinstance(duration, (int, float)):
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            return False, "Duration must be a number", None

    # Convert to integer
    try:
        duration_int = int(duration)
    except (TypeError, ValueError):
        return False, "Duration must be a valid integer", None

    # Range validation
    if duration_int <= 0:
        return False, "Duration must be positive", None

    # Maximum duration check (unless override allowed)
    if not allow_override and duration_int > MAX_DURATION:
        return False, f"Duration exceeds maximum of {MAX_DURATION//3600} hours ({MAX_DURATION} seconds). Use allow_override for longer recordings.", None

    # Reasonable upper bound even with override (prevent resource exhaustion)
    if duration_int > 86400:  # 24 hours
        return False, "Duration cannot exceed 24 hours (86400 seconds)", None

    return True, None, duration_int


def validate_string(value: Any, field_name: str, min_length: int = 0, max_length: int = 255,
                   allow_empty: bool = False, pattern: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate string input.

    Args:
        value: Value to validate
        field_name: Name of field for error messages
        min_length: Minimum string length
        max_length: Maximum string length
        allow_empty: If True, empty strings are valid
        pattern: Optional regex pattern to match

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, value_str: str|None)
    """
    # Type validation
    if not isinstance(value, str):
        if value is None:
            if allow_empty:
                return True, None, ""
            return False, f"{field_name} is required", None
        try:
            value = str(value)
        except:
            return False, f"{field_name} must be a string", None

    # Empty check
    if len(value) == 0 and not allow_empty:
        return False, f"{field_name} cannot be empty", None

    # Length validation
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters", None

    if len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters", None

    # Pattern validation
    if pattern and not re.match(pattern, value):
        return False, f"{field_name} format is invalid", None

    return True, None, value


def validate_boolean(value: Any, field_name: str) -> Tuple[bool, Optional[str], bool]:
    """
    Validate and convert boolean input.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, value_bool: bool)
    """
    if isinstance(value, bool):
        return True, None, value

    # Accept common boolean representations
    if isinstance(value, str):
        lower_val = value.lower()
        if lower_val in ('true', '1', 'yes', 'on'):
            return True, None, True
        if lower_val in ('false', '0', 'no', 'off'):
            return True, None, False

    if isinstance(value, (int, float)):
        return True, None, bool(value)

    return False, f"{field_name} must be a boolean value", False


def validate_ip_address(value: Any, field_name: str = "IP address") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate IP address format.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, ip_str: str|None)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string", None

    # IPv4 pattern
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'

    if not re.match(ipv4_pattern, value):
        return False, f"{field_name} must be a valid IPv4 address (e.g., 192.168.1.100)", None

    # Validate each octet
    octets = value.split('.')
    for octet in octets:
        try:
            num = int(octet)
            if num < 0 or num > 255:
                return False, f"{field_name} octets must be between 0 and 255", None
        except ValueError:
            return False, f"{field_name} octets must be numeric", None

    return True, None, value


def validate_path(value: Any, field_name: str = "Path", allow_relative: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate file path (basic check for path traversal attacks).

    Args:
        value: Value to validate
        field_name: Name of field for error messages
        allow_relative: If True, allow relative paths

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, path_str: str|None)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string", None

    # Check for path traversal attempts
    if '..' in value:
        return False, f"{field_name} cannot contain '..' (path traversal attempt)", None

    # Check for null bytes
    if '\x00' in value:
        return False, f"{field_name} contains invalid characters", None

    # If not allowing relative paths, must start with /
    if not allow_relative and not value.startswith('/'):
        return False, f"{field_name} must be an absolute path", None

    # Basic length check
    if len(value) > 4096:
        return False, f"{field_name} is too long (max 4096 characters)", None

    return True, None, value


def validate_iso_datetime(value: Any, field_name: str = "Datetime") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validate ISO format datetime string.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, datetime_str: str|None)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string", None

    # Try to parse as ISO datetime
    from datetime import datetime
    try:
        datetime.fromisoformat(value)
        return True, None, value
    except ValueError:
        return False, f"{field_name} must be in ISO format (e.g., 2024-01-15T14:30:00)", None


def validate_json(value: Any, field_name: str = "JSON") -> Tuple[bool, Optional[str], Any]:
    """
    Validate and parse JSON string.

    Args:
        value: Value to validate
        field_name: Name of field for error messages

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, parsed_value: Any)
    """
    if value is None:
        return True, None, None

    if not isinstance(value, str):
        # Already parsed
        return True, None, value

    import json
    try:
        parsed = json.loads(value)
        return True, None, parsed
    except json.JSONDecodeError as e:
        return False, f"{field_name} is not valid JSON: {str(e)}", None


def validate_request_data(data: dict, schema: dict) -> Tuple[bool, Optional[str], dict]:
    """
    Validate request data against a schema.

    Args:
        data: Request data dictionary
        schema: Schema dictionary with field definitions
            Example: {
                'duration': {'type': 'duration', 'required': True},
                'name': {'type': 'string', 'max_length': 100}
            }

    Returns:
        Tuple of (is_valid: bool, error_message: str|None, validated_data: dict)
    """
    validated = {}

    for field, rules in schema.items():
        value = data.get(field)
        required = rules.get('required', False)
        field_type = rules.get('type', 'string')

        # Check required fields
        if required and value is None:
            return False, f"Field '{field}' is required", {}

        # Skip validation if not required and not provided
        if value is None and not required:
            validated[field] = rules.get('default')
            continue

        # Type-specific validation
        if field_type == 'duration':
            valid, error, validated_value = validate_duration(
                value,
                allow_none=rules.get('allow_none', False),
                allow_override=rules.get('allow_override', False)
            )
        elif field_type == 'string':
            valid, error, validated_value = validate_string(
                value, field,
                min_length=rules.get('min_length', 0),
                max_length=rules.get('max_length', 255),
                allow_empty=rules.get('allow_empty', False),
                pattern=rules.get('pattern')
            )
        elif field_type == 'boolean':
            valid, error, validated_value = validate_boolean(value, field)
        elif field_type == 'ip':
            valid, error, validated_value = validate_ip_address(value, field)
        elif field_type == 'path':
            valid, error, validated_value = validate_path(value, field)
        elif field_type == 'datetime':
            valid, error, validated_value = validate_iso_datetime(value, field)
        elif field_type == 'json':
            valid, error, validated_value = validate_json(value, field)
        else:
            # Unknown type, pass through
            valid, error, validated_value = True, None, value

        if not valid:
            return False, error, {}

        validated[field] = validated_value

    return True, None, validated
