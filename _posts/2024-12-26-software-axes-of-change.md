---
layout: single
title:  "Designing Software Along Axes of Change"
tags:
  - documentation
---

Software is tough to design - not because programming itself is difficult, but because the technical requirements and user input are subject to change. As someone who is not a software engineer by training, cutting through the decision paralysis to design programs to accommodate change is one of the most difficult parts of programming. 

Seeing as I am not an expert, take this post with a ***heavy*** grain of salt, as it is primarily serving to document my thinking on software design.

## Types of Change
Change can take several forms, and it is important to define the types of change that are possible in a given program: 
1. Adding or removing options. Let’s say you allow a user to select from any of several options: A, B, or C. This could take the form of a drop-down box in a GUI, or a set of possible argument values to a function. How do you allow the user to add option D, or remove option C, that weren't originally included?

2. Adding or removing categories of options. This may take the form of the user adding a new drop-down box in a GUI, or a new keyword argument to a function.

## Defining Axes of Change
An "axis" of change is a way in which a program could or would need to change. This will depend on what the current requirements are for the program, the hierarchy of importance for those requirements, and an estimate of what kinds of changes could be needed to the program in the future.

Ranking the importance of each axis of change directly informs the design of a program. The order of each axis of change becomes the order of the control flow of the program.

For example, for a website like [Kayak](https://www.kayak.com) that allows people to search for flights across a variety of airlines, some of the axes of change may be:

1. Adding and removing airlines

2. Adding and removing types of airplanes

3. Adding and removing types of travel advisories

These items are axes of change because they consist of modifications to the original scope of the program. For example, perhaps in the beginning only the airlines United and American need to be included, but the design calls for being able to add and remove airlines with updates to the site.

Note that some of the primary user inputs such as dates, destinations, one-way or roundtrip, number of passengers, etc. are not in the above list. While of course the dates, destinations, number of passengers, etc. can change, that change is predictable and *part of the design*, and therefore are not axes of change for the purposes of software design.