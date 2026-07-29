#!/usr/bin/env python3
"""
Comprehensive Test Runner for Transkrybe.ai

This script replaces standalone validation scripts with integrated pytest tests
and provides multiple test execution modes for different scenarios.

Usage:
    python -m tests.run_tests            # Run all tests
    python -m tests.run_tests --validation   # Run validation tests only
    python -m tests.run_tests --smoke       # Run smoke tests only
    python -m tests.run_tests --quick       # Run quick tests only
    python -m tests.run_tests --coverage    # Run with coverage report
"""

import argparse
import sys
from pathlib import Path

import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_all_tests():
    """Run the complete test suite."""
    print("🧪 Running Transkrybe.ai Complete Test Suite")
    print("=" * 60)

    tests_dir = Path(__file__).parent

    pytest_args = [
        str(tests_dir),
        "-v",
        "--tb=short",
        "--durations=10",
        "-x",  # Stop on first failure for faster feedback
    ]

    exit_code = pytest.main(pytest_args)

    print("\\n" + "=" * 60)
    if exit_code == 0:
        print("✅ ALL TESTS PASSED!")
        print("🚀 Application is validated and ready for deployment!")
    else:
        print("❌ SOME TESTS FAILED!")
        print("🔧 Please fix issues before deployment.")

    return exit_code


def run_validation_tests():
    """
    Run validation tests that replace standalone validation scripts.

    These tests validate:
    - Module imports and dependencies
    - Configuration integrity
    - Application structure
    - Component functionality
    - Code quality checks
    """
    print("🔍 Running Application Validation Tests")
    print("=" * 50)
    print("📋 Validating: imports, config, structure, components...")

    tests_dir = Path(__file__).parent
    validation_dir = tests_dir / "test_integration"

    pytest_args = [str(validation_dir), "-v", "--tb=short", "--durations=5"]

    exit_code = pytest.main(pytest_args)

    print("\\n" + "=" * 50)
    if exit_code == 0:
        print("✅ VALIDATION PASSED!")
        print("📦 All modules, configuration, and structure validated!")
        print("🎯 Application integrity confirmed!")
    else:
        print("❌ VALIDATION FAILED!")
        print("⚠️  Fix critical issues before deployment!")

    return exit_code


def run_smoke_tests():
    """Run quick smoke tests for basic functionality."""
    print("💨 Running Quick Smoke Tests")
    print("=" * 35)

    tests_dir = Path(__file__).parent

    pytest_args = [
        str(tests_dir),
        "-v",
        "--tb=line",
        "-m",
        "smoke",
        "--maxfail=3",
        "--durations=3",
    ]

    exit_code = pytest.main(pytest_args)

    print("\\n" + "=" * 35)
    if exit_code == 0:
        print("✅ SMOKE TESTS PASSED!")
        print("⚡ Basic functionality confirmed!")
    else:
        print("❌ SMOKE TESTS FAILED!")
        print("🚨 Critical functionality issues detected!")

    return exit_code


def run_quick_tests():
    """Run quick tests (unit tests, fast integration tests)."""
    print("⚡ Running Quick Test Suite")
    print("=" * 40)

    tests_dir = Path(__file__).parent

    pytest_args = [
        str(tests_dir),
        "-v",
        "--tb=line",
        "-m",
        "not slow",
        "--maxfail=5",
        "--durations=5",
    ]

    exit_code = pytest.main(pytest_args)

    print("\\n" + "=" * 40)
    if exit_code == 0:
        print("✅ QUICK TESTS PASSED!")
    else:
        print("❌ QUICK TESTS FAILED!")

    return exit_code


def run_with_coverage():
    """Run tests with coverage reporting."""
    print("📊 Running Tests with Coverage Analysis")
    print("=" * 45)

    tests_dir = Path(__file__).parent

    pytest_args = [
        str(tests_dir),
        "-v",
        "--tb=short",
        "--cov=.",
        "--cov-report=html",
        "--cov-report=term",
        "--cov-report=xml",
        "--durations=10",
    ]

    exit_code = pytest.main(pytest_args)

    print("\\n" + "=" * 45)
    if exit_code == 0:
        print("✅ TESTS PASSED WITH COVERAGE!")
        print("📈 Coverage report generated in htmlcov/")
    else:
        print("❌ TESTS FAILED!")

    return exit_code


def run_category_tests(category):
    """Run tests for a specific category."""
    print(f"🎯 Running {category.upper()} Tests")
    print("=" * 40)

    tests_dir = Path(__file__).parent
    category_dir = tests_dir / f"test_{category}"

    if not category_dir.exists():
        print(f"❌ Test category '{category}' not found!")
        return 1

    pytest_args = [str(category_dir), "-v", "--tb=short", "--durations=5"]

    exit_code = pytest.main(pytest_args)

    print("\\n" + "=" * 40)
    if exit_code == 0:
        print(f"✅ {category.upper()} TESTS PASSED!")
    else:
        print(f"❌ {category.upper()} TESTS FAILED!")

    return exit_code


def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Transkrybe.ai Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m tests.run_tests                    # Run all tests
  python -m tests.run_tests --validation       # Validation tests only
  python -m tests.run_tests --smoke            # Quick smoke tests
  python -m tests.run_tests --coverage         # Tests with coverage
  python -m tests.run_tests --category=core    # Core tests only
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--validation",
        action="store_true",
        help="Run validation tests only (replaces validation scripts)",
    )
    group.add_argument("--smoke", action="store_true", help="Run smoke tests only")
    group.add_argument(
        "--quick", action="store_true", help="Run quick tests only (exclude slow tests)"
    )
    group.add_argument(
        "--coverage", action="store_true", help="Run tests with coverage reporting"
    )
    group.add_argument(
        "--category",
        choices=["api", "core", "data", "ui", "infrastructure", "integration"],
        help="Run tests for specific category only",
    )

    args = parser.parse_args()

    # Route to appropriate test runner
    if args.validation:
        return run_validation_tests()
    elif args.smoke:
        return run_smoke_tests()
    elif args.quick:
        return run_quick_tests()
    elif args.coverage:
        return run_with_coverage()
    elif args.category:
        return run_category_tests(args.category)
    else:
        return run_all_tests()


if __name__ == "__main__":
    sys.exit(main())
