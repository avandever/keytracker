#!/bin/sh -x
# Blackify python
find keytracker -name '*.py' | xargs black
# Beautify css
find keytracker/ -name '*.css' | xargs css-beautify -r
# Reformat templates
find keytracker/templates/ -name '*.html' | xargs djlint --reformat
# Lint templates
find keytracker/templates/ -name '*.html' | xargs djlint --lint
