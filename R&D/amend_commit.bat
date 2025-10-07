@echo off
rem Work-in-progress sync: fold all changes into the last commit and force-push.
rem Only the newest version of each binary (.hip/.hda) stays in history on GitHub.
rem Then drop the replaced commits locally too, so .git doesn't grow with every save.
rem Start a new topic with a normal "git commit -m ..." first, or it gets folded into the previous one.

git add --all
git commit --amend --no-edit
git push --force

git reflog expire --expire=now --all
git gc --prune=now --quiet
