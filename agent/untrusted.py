
"""
Wrap tool results so that untrusted content cannot escape the XML-like tags
injected into the model's context.

After json.dumps, the three characters that could break the wrapper tag
(<, >, &) are replaced with their JSON-safe Unicode escapes.  The JSON
remains valid and json.loads will decode the escapes back to the original
characters.
"""

import json


def wrap_untrusted(result) -> str:
    """
    Serialise result as JSON, escape tag-breaking characters, and wrap in
    an untrusted tool_result tag.

    The three replacements guarantee that no content inside the JSON can
    close or spoof the outer tag:
        <  ->  \\u003c
        >  ->  \\u003e
        &  ->  \\u0026
    """
    serialised = json.dumps(result, ensure_ascii=False)
    # Replace characters that would break XML-like wrapper tags.
    # These are valid JSON unicode escapes; json.loads decodes them correctly.
    serialised = serialised.replace("<", "\\u003c")
    serialised = serialised.replace(">", "\\u003e")
    serialised = serialised.replace("&", "\\u0026")
    return f'<tool_result untrusted="true">{serialised}</tool_result>'
