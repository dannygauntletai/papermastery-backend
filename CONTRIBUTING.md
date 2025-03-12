# Contributing to PaperMastery Backend

Thank you for your interest in contributing to the PaperMastery backend project! This guide will help you set up your development environment and understand our contribution workflow.

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Git

### Step 1: Clone the repository

```bash
git clone https://github.com/yourusername/papermastery-backend.git
cd papermastery-backend
```

### Step 2: Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install dependencies

Install both regular and development dependencies:

```bash
pip install -r requirements-dev.txt
```

### Step 4: Set up pre-commit hooks

```bash
pre-commit install
```

This will ensure that linting and formatting checks run automatically on each commit.

### Step 5: Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Then edit the `.env` file with your API keys and configuration.

## Development Workflow

### 1. Create a feature branch

```bash
git checkout develop
git pull
git checkout -b feature/your-feature-name
```

### 2. Make your changes

Implement your changes, following these guidelines:

- Follow the code style (PEP 8)
- Add tests for new functionality
- Update documentation as needed

### 3. Run tests

```bash
# Run all tests
python -m pytest

# Run specific tests
python -m pytest tests/test_specific_file.py

# Run tests with coverage
python -m pytest --cov=app tests/
```

### 4. Commit your changes

Make meaningful commits with clear messages:

```bash
git add .
git commit -m "feat: add your feature description"
```

Pre-commit hooks will automatically run to check your code. If any issues are found, fix them and commit again.

### 5. Push your changes and create a pull request

```bash
git push -u origin feature/your-feature-name
```

Then go to GitHub and create a pull request against the `develop` branch.

## Code Quality Tools

### Linting with Flake8

```bash
flake8 app tests
```

### Type checking with MyPy

```bash
mypy app
```

### Formatting with Black

```bash
black app tests
```

### Import sorting with isort

```bash
isort app tests
```

## Testing Guidelines

- Write tests for all new functionality
- Make sure all tests pass before submitting a pull request
- Test both success and failure cases
- Use mocks and fixtures for external dependencies
- Aim for high code coverage

## Documentation Guidelines

- Add docstrings to all new functions, classes, and modules
- Update the API documentation for any changes to endpoints
- Keep the README.md updated with new features or changes
- Add usage examples for new functionality

## Commit Message Guidelines

We follow the Conventional Commits specification:

- `feat:` - A new feature
- `fix:` - A bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring without functionality changes
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

## Getting Help

If you need help with your contribution:

1. Check the documentation in the `docs/` directory
2. Look for similar issues in the GitHub repository
3. Ask questions in your pull request or open a new issue

Thank you for contributing to PaperMastery! 