.PHONY: test clean
test:
	python3 -m runner.harness
clean:
	rm -rf bundles/outputs/*
