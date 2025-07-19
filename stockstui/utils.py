def slugify(name: str) -> str:
    """Converts a string to a snake_case identifier, safe for use as a file or category name."""
    return name.strip().lower().replace(" ", "_")

def extract_cell_text(cell) -> str:
    """
    Safely extracts the plain text content from a Rich renderable or a DataTable cell.

    Args:
        cell: The cell or renderable object.

    Returns:
        The extracted plain text as a string.
    """
    if not cell:
        return ""
    # Prefer the .plain attribute for Rich objects, fall back to str()
    return getattr(cell, 'plain', str(cell)).strip()

def parse_tags(tags_input: str) -> list[str]:
    """
    Parses a tag input string that can use space, comma, or semicolon separators.
    
    Args:
        tags_input: String containing tags separated by spaces, commas, or semicolons
        
    Returns:
        List of cleaned, deduplicated tags
    """
    if not tags_input or not tags_input.strip():
        return []
    
    # Replace semicolons and commas with spaces for unified splitting
    normalized = tags_input.replace(';', ' ').replace(',', ' ')
    
    # Split by whitespace and clean up
    tags = [tag.strip().lower() for tag in normalized.split() if tag.strip()]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags

def format_tags(tags: list[str]) -> str:
    """
    Formats a list of tags back to a comma-separated string for display.
    
    Args:
        tags: List of tag strings
        
    Returns:
        Comma-separated string of tags
    """
    if not tags:
        return ""
    return ", ".join(tags)

def match_tags(item_tags: list[str], filter_tags: list[str]) -> bool:
    """
    Checks if any of the filter tags match the item's tags.
    
    Args:
        item_tags: Tags associated with the item
        filter_tags: Tags to filter by
        
    Returns:
        True if any filter tag matches any item tag, False otherwise
    """
    if not filter_tags:
        return True  # No filter means show all
    
    if not item_tags:
        return False  # Hide untagged items when filtering for specific tags
    
    return bool(set(item_tags) & set(filter_tags))