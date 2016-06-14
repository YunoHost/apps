#!/usr/bin/bash

if [ ! $1 ] || [ $1 = "-h" ] || [ $1 = "--help" ]; then
echo "Specify builds apps list as parameters" ; exit
fi

pattern="\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,6}\b"

# Grep email addresses from builds apps lists arguments
grep -E -o $pattern $* | \

# Eclude example addresses
grep -v jon@doe.net | grep -vi domain | grep -v johndoe@example.com | \

# Remove file name when there is more than two arguments, sort, remove duplicate
cut -d : -f 2 | sort | uniq # | wc -l

# Get number of packagers: uncomment upper line
