#!/usr/bin/env bash

if [[ $# -ne 1 ]]
then
    echo "Usage: $0 rXX.yaml" >&2
    exit 1
fi

echo "credits:" >> $1
cat $1 | grep '/mnt/d/4K' | tr '.' ' ' | tr '/' ' ' | sed -r 's/.* mnt d 4K ([A-z]*) ([[:digit:]][[:digit:]]) ([[:digit:]][[:digit:]]) ([[:digit:]][[:digit:]]) ([[:alpha:]]* [[:alpha:]]*) (.*) XXX.*$/  - studio: \1\n    date: \2.\3.\4\n    title: \6\n    perfomers:\n      - \5/' | grep -v mnt >> $1
cat $1 | grep '/mnt/d/4K' | tr '.' ' ' | tr '/' ' ' | sed -r 's/.* mnt d 4K ([A-z]*) ([[:digit:]][[:digit:]]) ([[:digit:]][[:digit:]]) ([[:digit:]][[:digit:]]) ([[:alpha:]]* [[:alpha:]]*) XXX.*$/  - studio: \1\n    date: \2.\3.\4\n    perfomers:\n      - \5/' | grep -v mnt >> $1