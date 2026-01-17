"""
Neumann CLI Argument Parsing
"""

import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        description="neumann (neu) - universal constructor for code"
    )
    parser.add_argument("--system", type=str, default=None, help="Custom system prompt")
    parser.add_argument(
        "--tool-dir",
        type=str,
        default=None,
        help="Directory to load external tools from",
    )
    parser.add_argument(
        "--raw", action="store_true", help="Print raw API responses for debugging"
    )
    return parser.parse_args()
