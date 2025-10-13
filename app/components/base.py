"""
Base Component Class for GUSTAV UI Components

This module provides the foundation for all UI components in GUSTAV.
Using pure Python for HTML generation ensures type safety and better
IDE support compared to template engines.
"""

from typing import Optional, List, Dict, Any
import html


class Component:
    """Base class for all UI components in GUSTAV

    Benefits:
    - Type safety with IDE autocomplete
    - Easy testing with unit tests
    - No template language to learn
    - Automatic HTML escaping for security
    """

    def render(self) -> str:
        """Render the component as an HTML string

        Returns:
            str: HTML representation of the component
        """
        raise NotImplementedError("Subclasses must implement render()")

    @staticmethod
    def escape(text: Optional[str]) -> str:
        """Escape HTML entities to prevent XSS attacks

        Args:
            text: Text to escape (can be None)

        Returns:
            str: Escaped text or empty string if None
        """
        return html.escape(str(text)) if text is not None else ""

    @staticmethod
    def classes(*args: str, **conditionals: bool) -> str:
        """Helper to build CSS class strings with conditional classes

        Args:
            *args: Classes to always include
            **conditionals: Classes to include if value is True

        Returns:
            str: Space-separated class string

        Example:
            >>> Component.classes("btn", "btn-primary", disabled=True, active=False)
            "btn btn-primary disabled"
        """
        classes = list(args)
        classes.extend(key for key, value in conditionals.items() if value)
        return " ".join(classes)

    @staticmethod
    def attributes(**attrs: Any) -> str:
        """Build HTML attributes from keyword arguments

        Args:
            **attrs: Attribute key-value pairs

        Returns:
            str: HTML attribute string

        Example:
            >>> Component.attributes(id="test", data_value="123", disabled=True)
            'id="test" data-value="123" disabled'
        """
        result = []
        for key, value in attrs.items():
            # Special-case trailing underscore for reserved names: class_ -> class, for_ -> for
            if key.endswith("_"):
                key = key[:-1]
            else:
                # Convert inner underscores to hyphens (data_value -> data-value)
                key = key.replace("_", "-")

            if value is True:
                # Boolean attribute
                result.append(key)
            elif value is not False and value is not None:
                # Regular attribute
                result.append(f'{key}="{html.escape(str(value))}"')

        return " ".join(result)
