.PHONY: test run clean

run:
	python3 -m runner.harness

test:
	python3 -m pytest tests/ -v

test-cov:
	python3 -m pytest tests/ -v --cov=runner --cov=adapters --cov-report=term-missing

clean:
	rm -rf bundles/outputs/* __pycache__ .pytest_cache
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
