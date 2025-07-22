#!/usr/bin/env python3
from clang.cindex import Index, CursorKind, TranslationUnit, Config, Cursor
from typing import List, Tuple
import sys
import argparse

def print_node_tree(node: Cursor, indent=0):
    """Recursively print the AST node tree starting from the given node."""
    text = node.spelling or node.displayname
    kind = str(node.kind)[str(node.kind).index('.')+1:]
    print('// ' + '  ' * indent + f"{kind}: {text} [{node.location}]")

    for child in node.get_children():
        print_node_tree(child, indent + 1)

def parse_cppfile(cpp_file: str) -> TranslationUnit:
    """Parse a C++ file and extract enum values with their comments."""
    index = Index.create()
    tu = index.parse(cpp_file,
                     options=TranslationUnit.PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION |
                     TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD,
                     args=['-x', 'c++'])
    return tu

def get_enumclass_with_namespace(node: Cursor, current_ns: str = "") -> List[Tuple[Cursor, str]]:
    results = []

    for child in node.get_children():
        if child.kind == CursorKind.ENUM_DECL and child.is_definition():
            results.append((child, current_ns))
        elif child.kind == CursorKind.NAMESPACE:
            # Build namespace path (handle nested namespaces)
            new_ns = f"{current_ns}::{child.spelling}" if current_ns else child.spelling
            results.extend(get_enumclass_with_namespace(child, new_ns))

    return results

def generate_namespace_header(namespace_path: str) -> str:

    """Convert a namespace path like 'A::B::C' into opening namespace declarations.

    Example:
        'A::B::C' -> 'namespace A { namespace B { namespace C {'
        '' -> ''
    """
    if not namespace_path:
        return ""

    parts = namespace_path.split("::")
    return "".join(f"namespace {part} {{\n" for part in parts)

def generate_namespace_footer(namespace_path: str) -> str:
    """Generate closing braces for a namespace path.

    Example:
        'A::B::C' -> '} } }'
        '' -> ''
    """
    if not namespace_path:
        return ""

    parts = namespace_path.split("::")
    return "".join(f"}} // namespace {part}\n" for part in reversed(parts))



def generate_error_msg_function(enum: Cursor) -> str:
    """Generate the error_msg function implementation."""

    enum_name = enum.spelling
    items_name = {
        item.spelling: item.spelling
        for item in enum.get_children()
        if item.kind == CursorKind.ENUM_CONSTANT_DECL
    }

    function_name = f"error_msg_{enum_name.lower()}"

    code = f"""const char* {function_name}({enum_name} err) {{
    switch(err) {{
"""

    for key, value in items_name.items():
        code += f"        case {enum_name}::{key}: return \"{key}\";\n"

    code += f"""        default: return "Unknown error";
    }}
}}
"""
    return code


def main():
    parser = argparse.ArgumentParser(description='Generate error messages from C++ enum class.')
    parser.add_argument('cpp_file', help='Path to the C++ source file containing the enum class')
    parser.add_argument('--library-path', default='/usr/lib/llvm-14/lib',
                        help='Path to the LLVM library (default: /usr/lib/llvm-14/lib)')

    args = parser.parse_args()

    Config.set_library_path(args.library_path)

    try:
        tu = parse_cppfile(args.cpp_file)
        enums_and_ns = get_enumclass_with_namespace(tu.cursor)
        print("// Auto-generated error_msg function\n")
        print(f"#include \"{args.cpp_file}\"\n")
        for enum, ns in enums_and_ns:
            print(generate_namespace_header(ns))
            # print_node_tree(enum)
            # print()
            print(generate_error_msg_function(enum))
            print(generate_namespace_footer(ns))

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
