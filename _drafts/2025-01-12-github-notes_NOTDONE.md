---
layout: single
title:  "Notes on Git and GitHub"
tags:
  - documentation
---

There are several Git branching strategies, such as Gitflow, trunk-based development, or a feature branching strategy.

Here's a good intro article: https://neurathsboat.blog/post/git-intro/

Here's branching strategies from the Git documentation: https://git-scm.com/book/en/v2/Distributed-Git-Distributed-Workflows#ch05-distributed-git

Another good Git reference: https://swcarpentry.github.io/git-novice/

Lots of great info in slides here: https://alexslemonade.github.io/2023-chop-training/workshop-schedule.html

# Merges and Merge Conflicts
First and foremost, the [official GitHub documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/addressing-merge-conflicts/about-merge-conflicts) is a good introduction to this topic. you can abort a merge at any point during the merge resolution process using `git merge --abort`. This will leave you in exactly the same position as you were before you started the merge.

When you have a merge conflict, you can use `git status` to see which files have conflicts.

"Current change" refers to the modifications made on your local branch, while "incoming change" refers to the modifications made on the remote branch.

# How to Create a New Local and Remote Repository
## 1. Download the GitHub CLI
```bash
brew install gh
```

## 2. Set global git config
Before creating new repos, you should run `git config --global init.defaultBranch "main"` to ensure that your branch naming conventions are aligned with current best practices.

Also, run `git config --global push.autoSetupRemote true` to automatically set up a remote for the main branch when you create a new repository.

## 3. Initialize the local repository
```bash
git init
```
I like to add the local repository rather than creating the repo on GitHub and the computer at the same time. It's a more reliable workflow, and makes it more explicit which folder the repo will be created in.

## 4. Create the remote repository on GitHub
```bash
gh repo create "REPO_NAME" --public --source .
```
By having the `--source .` flag, the current directory will be used as the source for the new repository.