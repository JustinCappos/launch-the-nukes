#!/usr/bin/env python3
"""
Test runner script for launch-the-nukes project.
"""

import sys
import subprocess
import os

def run_tests(test_category=None, verbose=True, coverage=False):
    """
    Run tests with specified options.
    
    Args:
        test_category: Specific test category to run (yaml, flask, mcp, all)
        verbose: Whether to run tests in verbose mode
        coverage: Whether to generate coverage report
    """
    
    # Build pytest command
    cmd = ["python3", "-m", "pytest"]
    
    if test_category and test_category != "all":
        if test_category == "yaml":
            cmd.extend(["tests/test_yaml_parsing.py", "tests/test_yaml_factory.py"])
        elif test_category == "flask":
            cmd.extend(["tests/test_flask_app.py"])
        elif test_category == "mcp":
            cmd.extend(["tests/test_mcp_integration.py"])
        else:
            print(f"Unknown test category: {test_category}")
            print("Available categories: yaml, flask, mcp, all")
            return False
    else:
        cmd.append("tests/")
    
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=term-missing", "--cov-report=html:htmlcov"])
    
    # Run tests
    print(f"Running tests: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    return result.returncode == 0

def main():
    """Main test runner function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run tests for launch-the-nukes project")
    parser.add_argument("--category", choices=["yaml", "flask", "mcp", "all"], 
                       default="all", help="Test category to run")
    parser.add_argument("--quiet", action="store_true", help="Run tests quietly")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    
    args = parser.parse_args()
    
    # Run tests
    success = run_tests(
        test_category=args.category,
        verbose=not args.quiet,
        coverage=args.coverage
    )
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 