#!/bin/bash
# Development environment setup script
# Run this after cloning the repository

set -e

echo "Setting up development environment..."

# Install dependencies
echo "Installing dependencies..."
uv sync --dev

# Configure git hooks
echo "Configuring git hooks..."
git config core.hooksPath .githooks

echo "Setup complete!"
echo ""
echo "Git hooks configured:"
echo "  - pre-commit: runs ruff format, ruff check, and pyright on staged files"
