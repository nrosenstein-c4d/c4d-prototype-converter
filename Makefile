
.PHONY: default
default:
	@echo "available commands:"
	@echo "  clean"
	@echo "  dist"

clean:
	rm -v $(shell find -iname *.pyc)

dist:
	c4ddev pypkg
	tar -cvzf c4d_prototype_converter-$(shell git describe --tags).tar.gz \
			--exclude *.pyc --exclude *.afdesign \
			c4d_prototype_converter bootstrapper.pyp lib*.egg README.md LICENSE.txt
