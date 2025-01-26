---
layout: single
title:  "Adding GitHub comments to this website"
tags:
  - documentation
---

I came across [Giscus](https://giscus.app) at the bottom of a [Cosma listing on kausalflow.com](https://tools.kausalflow.com/tools/cosma/). Giscus provides a simple way to add GitHub comments to a Jekyll website (like this one). This allows anyone to comment on my website using GitHub Discussions! The setup process was surprisingly simple, only taking me about 10-15 minutes to complete and troubleshoot.

To add comments via GitHub Discussions to an [academic pages](https://academicpages.github.io) website (like this one), go to [Giscus](https://giscus.app) and follow the step by step instructions in the configuration section. Be sure that the repository meets all three criteria listed in the `Repository` section for Giscus to work.

## Step by Step Instructions on https://giscus.app
1. `Repository` section: Enter the repository name (e.g. `mtillman14/mtillman14.github.io`).
2. `Page <-> Discussion`: I recommend leaving the default.
3. `Discussion Category`: I recommend either creating a new `Comments` category in your GitHub repo's Discussions (be sure to set its type to `Announcements`), or using the `Announcements` category that Giscus recommends.
4. `Features`: I only selected `Enable reactions for the main post` and left the others blank.
5. `Theme`: I left the default `Preferred color scheme`.

## Adding the Giscus script to the Academic Pages website
1. In the `_includes/comments-providers/custom.html` file, paste the Giscus script from the Giscus website. It should be customized to your repository information after filling out the configuration.
2. In the `_config.yml` file, set `comments.provider` to `"custom"`.

That's it! After committing and pushing these changes, you should see a comments section at the bottom of your posts. Moderating these posted comments can be done by editing/deleting posts in the GitHub Discussions section of your repository.