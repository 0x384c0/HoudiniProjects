#!/bin/bash
set -e

git add --all
git commit --amend --no-edit
git push --force
