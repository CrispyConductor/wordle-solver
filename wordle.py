"""
This is a solver utility for the Wordle game https://www.powerlanguage.co.uk/wordle/ .
Run it with -h for help.
This requires a newline-separate file with dictionary words in ./words.txt.
"""

import re
import random
import argparse

ALL_LETTERS = 'abcdefghijklmnopqrstuvwxyz'

class WordleSolver:

    def __init__(self, wordlen: int = 5, dictfile: str = './words.txt', allow_dup_letters: bool = False):
        self.wordlen = wordlen
        self._load_words(dictfile, allow_dup_letters)
        self.reset()

    def _load_words(self, dictfile: str, allow_dup_letters: bool) -> None:
        """Loads and filters words from a file."""
        with open(dictfile, 'r') as f:
            all_words = [ re.sub(r'[^a-z]', '', line.lower().strip()) for line in f ]
        all_words = [ word for word in all_words if len(word) == self.wordlen ]
        # Remove words with duplicate letters (I assume these are disallowed)
        def has_dup_letters(word):
            letterset = set()
            for l in word:
                if l in letterset:
                    return True
                letterset.add(l)
            return False
        if not allow_dup_letters:
            all_words = [ word for word in all_words if not has_dup_letters(word) ]
        self.all_words = all_words

    def reset(self) -> None:
        """Resets state variables related to a wordle session."""
        # A list (length self.wordlen) of sets; the current set of allowable letters at each position.
        self.positions = []
        for i in range(self.wordlen):
            self.positions.append(set(ALL_LETTERS))
        # Set of letters for which positions are known
        self.known_letters = set()
        # Set of letters that are present in the word but positions are not known
        self.reloc_letters = set()
        # Set of letters that are known to not be in the word
        self.exclude_letters = set()
        # Set of letters about which no information is known
        self.unknown_letters = set(ALL_LETTERS)
        # Set of words that have been tried so far
        self.tried_words = set()
        self.tried_word_list = []
        # Set of words that might be possible solutions at this point
        self.potential_solutions = set(self.all_words)
        self._update_potential_solutions()
        # Flag indicating if target has been solved
        self.solved = False

    def update(self, guessed_word: str, result: str) -> None:
        """Updates the state with the result of a guess.

        Parameters:
            guessed_word -- The word that was guessed
            result -- A string of same length as guessed_word containing feedback codes.  Each
                char must be one of:
                'C' - Letter is correct and in the correct position
                'L' - Letter is in the word but wrong position
                'X' - Letter is not in the word
        """
        assert(len(guessed_word) == self.wordlen)
        assert(len(result) == self.wordlen)
        for i, letter in enumerate(guessed_word):
            self.unknown_letters.discard(letter)
            if result[i].upper() == 'C':
                self.positions[i] = set([ letter ])
                self.reloc_letters.discard(letter)
                self.known_letters.add(letter)
            elif result[i].upper() == 'L':
                self.positions[i].discard(letter)
                if letter not in self.known_letters:
                    self.reloc_letters.add(letter)
            elif result[i].upper() == 'X':
                for s in self.positions:
                    s.discard(letter)
                self.exclude_letters.add(letter)
            else:
                raise Exception('Invalid result code ' + result)
        self.tried_words.add(guessed_word)
        self.tried_word_list.append(guessed_word)
        if len(self.reloc_letters) + len(self.known_letters) >= self.wordlen:
            # We know all letters that are in word, so there are no unknown letters, and everything else is excluded
            self.unknown_letters = set()
            self.exclude_letters = set(ALL_LETTERS) - self.known_letters - self.reloc_letters
        self._update_potential_solutions()
        if result == 'C' * self.wordlen:
            # Correct result was guessed
            self.solved = True
            self.potential_solutions = set([ guessed_word ])

    def _update_potential_solutions(self) -> None:
        """Recalculates self.potential_solutions according to current state."""
        # Filter the set of potential solutions according to which letters are allowed in which positions.
        # Do this by constructing a regex from self.positions
        regex_str = ''.join([
            '[' + ''.join(list(letterset)) + ']'
            for letterset in self.positions
        ])
        rx = re.compile(regex_str)
        # Also ensure that all reloc_letters are present somewhere in the word and that the word has not been tried.
        self.potential_solutions = set((
            word
            for word in self.potential_solutions
            if
                rx.fullmatch(word) and
                word not in self.tried_words and
                all(( letter in word for letter in self.reloc_letters ))
        ))

    def get_guess(self) -> str:
        if len(self.potential_solutions) == 0:
            # There are no possible solutions
            raise Exception('Answer unknown')
        elif len(self.potential_solutions) <= 2:
            # Either there's 1 possible solution left (in which case it should be the answer), or
            # there are 2 left, and we just need to try each one.  Either way, return the first.
            return list(self.potential_solutions)[0]

        # At this point, more info is needed.  We can pick a word not in potential_solutions if it optimizes the info we get.
        # We ideally want to pick a word that contains all of reloc_letters (in positions they might be in) and none of exclude_letters.
        # We also don't want to use known_letters in their respective positions, because we already know that info.  Instead,
        # use these slots to get additional reloc_letters or exclude_letters.  Prioritize letters to try here based on ones that
        # will best segment the remaining potential_solutions (when we discover whether or not the letter exists in the word).

        # For each unknown letter (not known if present or not in the word), calculate the fraction of potential_solutions it appears in.
        # This dict is a mapping from letter to the fraction of potential_solutions words the letter appears in.
        letter_presence_dict = {
            letter : sum(( 1 if letter in w else 0 for w in self.potential_solutions )) / len(self.potential_solutions)
            for letter in ALL_LETTERS
        }

        # Score each word in all_words the fits the requirements, and use the one with the highest score.
        # Selected word must contain all of reloc_letters in valid (untried) positions.
        # Other positions (both for known_letters and unknown_letters) are scored based on the amount of info that
        # position could reveal.  If if's a letter that's already known for that spot, or a letter that's known
        # to be excluded, then no additional information is discovered.

        # This regex filters out words that have reloc_letters in positions they can't be in
        regex_str = ''.join([
            '[' + ''.join(list(letterset.union(self.exclude_letters).union(self.known_letters).union(self.unknown_letters))) + ']'
            for letterset in self.positions
        ])
        rx = re.compile(regex_str)

        # Track the best word/score so far
        best_word = None
        best_score = -1

        for word in self.all_words:
            # Make sure it contains all reloc_letters in valid positions and hasn't been tried
            if not rx.fullmatch(word) or not all(( letter in word for letter in self.reloc_letters )) or word in self.tried_words:
                continue
            # Tally a score for each slot
            score = 0 if word not in self.potential_solutions else 0.01 # small score boost to prefer solutions that are candidates
            for i, letter in enumerate(word):
                if letter in self.known_letters or letter in self.exclude_letters:
                    # If we already know the position of this letter (or that it isn't present at all), it gives us no useful info.
                    lscore = 0
                else:
                    # Score based on preference for letters that best bisect the potential solutions.
                    # NOTE: This can probably be done more optimally by taking into account the other letters in the word.
                    lscore = 0.5 - abs(letter_presence_dict[letter] - 0.5)
                    # Reduce score if letter has already been used in word (won't provide relocs info)
                    if letter in word[:i]:
                        lscore /= 5
                score += lscore

            if score > best_score:
                best_score = score
                best_word = word

        return best_word

    @staticmethod
    def get_word_result(guess: str, target: str) -> str:
        """Returns the result string generated by comparing a guessed word to the correct target word."""
        r = ''
        for i in range(len(target)):
            l = guess[i]
            if target[i] == l:
                r += 'C'
            elif l in target:
                r += 'L'
            else:
                r += 'X'
        return r

    def run_auto(self, target_word: str) -> int:
        """Runs the game trying to guess a given target word.  Returns the number of guesses required."""
        self.reset()
        nguesses = 0
        while True:
            nguesses += 1
            guess = self.get_guess()
            if guess == target_word: break
            res = WordleSolver.get_word_result(guess, target_word)
            self.update(guess, res)
        return nguesses


def run_interactive():
    solver = WordleSolver()
    while True:
        guess = solver.get_guess()
        print('Guess: ' + guess)
        if len(solver.potential_solutions) == 1:
            print('That\'s the last possible solution in this dictionary.')
            return
        res = input('Feedback (C/L/X = Correct position/Wrong position/Letter unused): ')
        solver.update(guess, res)
        if solver.solved:
            return

def run_target(target):
    solver = WordleSolver()
    nguesses = solver.run_auto(target)
    print(f'Guessed word {target} in {nguesses} guesses:')
    print('\n'.join(solver.tried_word_list))
    print(target)

def run_eval():
    solver = WordleSolver()
    wlist = solver.all_words.copy()
    random.shuffle(wlist)
    histogram = {}
    failed_words = []
    nwords = 0
    totalguesses = 0
    for word in wlist:
        nguesses = solver.run_auto(word)
        print('Target word', word, 'num guesses', nguesses)
        histogram[nguesses] = histogram.get(nguesses, 0) + 1
        if nguesses > 6:
            failed_words.append(word)
        nwords += 1
        totalguesses += nguesses
    print('nguesses histogram:')
    for nguesses, cnt in sorted(list(histogram.items()), key=lambda tup: tup[0]):
        print(f'{nguesses} guesses: {cnt} words')
    print('Failed words:', failed_words)
    print('Average guesses:', totalguesses / nwords)


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='Wordle Solver')
    argparser.add_argument('-i', action='store_true', help='Interactive solver mode')
    argparser.add_argument('-w', action='store', help='Solve target word mode')
    argparser.add_argument('-e', action='store_true', help='Evaluation/auto mode')
    args = argparser.parse_args()

    if args.i:
        assert(not args.e)
        assert(not args.w)
        run_interactive()

    elif args.w:
        assert(not args.e)
        assert(isinstance(args.w, str))
        run_target(args.w)

    elif args.e:
        run_eval()

    else:
        raise Exception('Must supply one of -h, -i, -w <Target>, -e')



