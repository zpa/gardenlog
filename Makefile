all: test.db

clean:
	rm test.db

test.db:
	touch $@
	python3 populate-database.py
