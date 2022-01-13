# Crispy's Wordle Solver

This is my attempt at a [Wordle](https://www.powerlanguage.co.uk/wordle/) solver.  It attempts to guess words to maximize information gain.  This algorithm is not completely optimal, but I believe it's pretty close.

Usage:

```
$ # Interactive solver
$ python3 wordle.py -i
Guess: roate
Enter feedback string using letters C, L, X.  Enter ! to blacklist word.  Or, to specify the word to guess: <word> <feedback>
Feedback (C/L/X = Correct position/Wrong position/Letter unused): LXXXX
Guess: sculk
Enter feedback string using letters C, L, X.  Enter ! to blacklist word.  Or, to specify the word to guess: <word> <feedback>
Feedback (C/L/X = Correct position/Wrong position/Letter unused): XXXXC
Guess: drink
Enter feedback string using letters C, L, X.  Enter ! to blacklist word.  Or, to specify the word to guess: <word> <feedback>
Feedback (C/L/X = Correct position/Wrong position/Letter unused): CCCCC

$ # Target word solver mode
$ python3 wordle.py -w joker
Guessed word joker in 3 guesses:
roate
mawks
joker

$ # Evaluation mode - tries to guess every word in the solution candidates dictionary
$ python3 wordle.py -e
...
nguesses histogram:
2 guesses: 55 words
3 guesses: 1123 words
4 guesses: 1098 words
5 guesses: 39 words
Failed words: []
Average guesses: 3.4842332613390927
Successful words: 2315/2315 (100.0%)
```

This solver has the ability to use separate dictionaries for solution candidates and for allowed guesses; at a glance, this appears to be what Wordle does, and the two respective dictionaries included here are extracted from the Wordle source code.

The algorithm works by tracking all possible solutions that fit the evidence gathered so far.  For each possible guess, that guess is evaluated in the context of each remaining potential solution, and potential solutions are clustered based on the resulting evidence (with respect to the guess word being evaluated).  From this, the average expected remaining solution set size (after the potential guess is submitted) is calculated for each guess word, and the guess that results in the lowest average expected remaining solution set size is selected.

This algorithm optimizes for maximally reducing the possible solution set size with each guess.  It should be pretty close to optimal, but doesn't take into account the possibility that some solution sets may be more effectively segmented in future guesses than others.  Taking this into account would likely require running the current algorithm inside of some kind of breadth-first-search; but the algorithm already isn't the speediest thing in the world, and I suspect the potential gains from implementing this would be minimal.


