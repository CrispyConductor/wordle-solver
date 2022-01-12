# Crispy's Wordle Solver

This is my attempt at a [Wordle](https://www.powerlanguage.co.uk/wordle/) solver.  It attempts to guess words to maximize information gain.  The algorithm is known to currently be suboptimal, but does pretty well in most cases.

Usage:

```
$ # Interactive solver
$ python3 wordle.py -i
Guess: arise
Feedback (C/L/X = Correct position/Wrong position/Letter unused): XCCXX
Guess: pinky
Feedback (C/L/X = Correct position/Wrong position/Letter unused): XLLLX
Guess: drink
Feedback (C/L/X = Correct position/Wrong position/Letter unused): CCCCC

$ # Target word solver mode
$ python3 wordle.py -w hired
Guessed word hired in 4 guesses:
arise
tired
wharf
hired

$ # Evaluation mode
$ python3 wordle.py -e
...
nguesses histogram:
1 guesses: 1 words
2 guesses: 79 words
3 guesses: 1033 words
4 guesses: 1165 words
5 guesses: 453 words
6 guesses: 118 words
7 guesses: 7 words
Failed words: ['james', 'fakes', 'caked', 'caves', 'foxed', 'meals', 'waxes']
Average guesses: 3.830532212885154
```

