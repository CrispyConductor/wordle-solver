"""
This is a solver utility for the Wordle game https://www.powerlanguage.co.uk/wordle/ .
Run it with -h for help.
This requires a newline-separate file with dictionary words in ./words.txt.
"""

import re
import random
import argparse
from collections.abc import Sequence, Mapping, Iterable
from typing import Optional
from array import array

ALL_LETTERS = 'abcdefghijklmnopqrstuvwxyz'

class WordleSolver:

    def __init__(self, wordlen: int = 5, dictfile_solutions: str = './words_wordle_solutions.txt', dictfile_guesses: Optional[str] = './words_wordle.txt', allow_dup_letters: bool = True, hard_mode: bool = False, const_first_guess: Optional[str] = 'roate'):
        self.wordlen = wordlen
        self.hard_mode = hard_mode
        self.all_solution_words = self._load_words(dictfile_solutions, allow_dup_letters)
        if dictfile_guesses == None:
            self.all_guess_words = self.all_solution_words.copy()
        else:
            self.all_guess_words = self._load_words(dictfile_guesses, allow_dup_letters)
        self._fast_word_result_buf = array('b', [ 0 for i in range(256) ])
        self.const_first_guess = const_first_guess
        self.reset()

    def _load_words(self, dictfile: str, allow_dup_letters: bool) -> None:
        """Loads and filters words from a file."""
        with open(dictfile, 'r') as f:
            #all_words = [ re.sub(r'[^a-z]', '', line.lower().strip()) for line in f ]
            all_words = [ line.lower().strip() for line in f if re.fullmatch(r'[a-z]+', line.strip()) ]
        all_words = [ word for word in all_words if len(word) == self.wordlen ]
        # Remove duplicate words (dups can occur after normalizing)
        all_words = list(set(all_words))
        # Remove words with duplicate letters
        def has_dup_letters(word):
            letterset = set()
            for l in word:
                if l in letterset:
                    return True
                letterset.add(l)
            return False
        if not allow_dup_letters:
            all_words = [ word for word in all_words if not has_dup_letters(word) ]
        return all_words

    @staticmethod
    def _get_letter_counts(word: str, all_letters: bool = False) -> dict[str, int]:
        """Returns a dict mapping each letter to counts of its occurrences."""
        r = { l : 0 for l in ALL_LETTERS } if all_letters else {}
        for l in word:
            r[l] = r.get(l, 0) + 1
        return r

    @staticmethod
    def _get_letter_count_ranges_of_words(words: Sequence[str]) -> dict[str, tuple[int, int]]:
        """Given a list of words, returns a dict of the range of letter counts, inclusive, that could be in a word."""
        r = {}
        for word in words:
            for letter, count in WordleSolver._get_letter_counts(word, True).items():
                if letter in r:
                    c = r[letter]
                    if count < c[0]:
                        c = (count, c[1])
                    if count > c[1]:
                        c = (c[0], count)
                    r[letter] = c
                else:
                    r[letter] = (count, count)
        for letter in ALL_LETTERS:
            if letter not in r:
                r[letter] = (0, 0)
        return r

    def reset(self) -> None:
        """Resets state variables related to a wordle session."""
        # A list (length self.wordlen) of sets; the current set of allowable letters at each position.
        self.positions = []
        for i in range(self.wordlen):
            self.positions.append(set(ALL_LETTERS))
        # Map from each letter to a tuple of the upper and lower bound (inclusive) of how many of that letter may be present
        self.letter_counts = WordleSolver._get_letter_count_ranges_of_words(self.all_solution_words)
        # Set of words that have been tried so far
        self.tried_words = set()
        self.tried_word_list = []
        # Set of words that might be possible solutions at this point
        self.potential_solutions = set(self.all_solution_words)
        # Flag indicating if target has been solved
        self.solved = False
        # Queue of constant first words to guess
        self.first_word_queue = [ self.const_first_guess ] if self.const_first_guess and self.const_first_guess in self.all_guess_words else []
        # The set of words that can be guessed is reset each time because it is modified in hard more
        self.potential_guesses = set(self.all_guess_words)

    def _fast_word_result(self, guess: str, target: str):
        """Faster word evaluation for internal use"""
        retval = 0
        target_lcounts = self._fast_word_result_buf
        for i in range(self.wordlen):
            target_lcounts[ord(target[i])] += 1
        placeval = 1
        for i in range(self.wordlen):
            if guess[i] == target[i]:
                retval += placeval * 2
                target_lcounts[ord(target[i])] -= 1
            placeval *= 3
        placeval = 1
        for i in range(self.wordlen):
            g = guess[i]
            t = target[i]
            ordg = ord(g)
            if g != t and target_lcounts[ordg] > 0:
                retval += placeval
                target_lcounts[ordg] -= 1
            placeval *= 3
        for i in range(self.wordlen):
            target_lcounts[ord(target[i])] = 0
        return retval

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
        assert(re.fullmatch(r'[CLX]+', result))
        # Count number of each letter in the guessed word dict[str, int]
        guess_lcounts = WordleSolver._get_letter_counts(guessed_word, True)
        # Count number of each letter confirmed to be in the solution
        result_lcounts = { l : 0 for l in ALL_LETTERS }
        for letter, rchar in zip(guessed_word, result):
            if rchar == 'C' or rchar == 'L':
                result_lcounts[letter] += 1
        # Update self.letter_counts accounting for new information
        for letter in guess_lcounts:
            gc = guess_lcounts[letter]
            rc = result_lcounts[letter]
            crange = self.letter_counts[letter]
            assert(gc >= rc)
            if gc > rc:
                # We guessed more of this letter than there are, so now we know how many of this letter there are exactly
                crange = (rc, rc)
            else:
                # Each instance of the letter we guessed is in the word, so this sets a lower bound on that letter count
                crange = (rc, crange[1])
            self.letter_counts[letter] = crange
        # Update self.positions according to position info in the result
        for i, (letter, rchar) in enumerate(zip(guessed_word, result)):
            if rchar == 'C':
                # This is the only letter that can be in this position
                self.positions[i] = set([ letter ])
            else:
                # We know this letter cannot exist in this position
                self.positions[i].discard(letter)
        # If the sum of all lower bounds on letter counts equals the word length, we know every letter in the word
        lbound_sum = sum(( lbound for lbound, ubound in self.letter_counts.values() ))
        if lbound_sum >= self.wordlen:
            # All letters' ubounds can be set to their lbounds
            self.letter_counts = { letter : ( lbound, lbound ) for letter, (lbound, ubound) in self.letter_counts.items() }
        # Update self.positions to take into account cases where we know all positions of a letter.
        # This also handles removing letters which cannot be in the solution.
        # NOTE: This could be improved by also considering positions with limited sets of potential letters
        for letter, (lbound, ubound) in self.letter_counts.items():
            # Count positions for which this letter is the only possibility
            nexclusive = sum(( 1 if letter in lset and len(lset) == 1 else 0 for lset in self.positions ))
            if nexclusive >= ubound:
                # We know all the places for this letter, it cannot occur in any other positions
                for lset in self.positions:
                    if not (letter in lset and len(lset) == 1):
                        lset.discard(letter)
        # Track the guessed words
        self.tried_words.add(guessed_word)
        self.tried_word_list.append(guessed_word)
        # Update the list of valid solutions at this point
        self._filter_words_by_known_info(self.potential_solutions)
        # If in hard mode, also filter potential guesses by known info
        if self.hard_mode:
            self._filter_words_by_known_info(self.potential_guesses)
        # After narrowing down potential solutions, letter count ranges may be narrowed as well
        self.letter_counts = WordleSolver._get_letter_count_ranges_of_words(list(self.potential_solutions))
        # Check if the guessed word was the correct solution
        if result == 'C' * self.wordlen:
            # Correct result was guessed
            self.solved = True
            self.potential_solutions = set([ guessed_word ])

    def _filter_words_by_known_info(self, words: set[str]) -> None:
        """Removes words from the set that do not fit known information."""
        # Filter the set of potential solutions according to which letters are allowed in which positions.
        # Do this by constructing a regex from self.positions
        regex_str = ''.join([
            '[' + ''.join(list(letterset)) + ']'
            for letterset in self.positions
        ])
        rx = re.compile(regex_str)
        # Filter potential_solutions by this regex, and also make sure letter counts are in bounds for each
        def word_within_bounds(word):
            lcounts = WordleSolver._get_letter_counts(word, True)
            for letter, lcount in lcounts.items():
                lbound, ubound = self.letter_counts[letter]
                if not (lbound <= lcount <= ubound):
                    return False
            return True
        for word in list(words):
            if not (rx.fullmatch(word) and word not in self.tried_words and word_within_bounds(word)):
                words.discard(word)

    def get_guess(self) -> str:
        # Handle constant first word(s)
        if len(self.first_word_queue):
            return self.first_word_queue.pop(0)

        if len(self.potential_solutions) == 0:
            # There are no possible solutions
            raise Exception('Answer unknown')
        elif len(self.potential_solutions) <= 2:
            # Either there's 1 possible solution left (in which case it should be the answer), or
            # there are 2 left, and we just need to try each one.  Either way, return the first.
            return list(self.potential_solutions)[0]

        # Determine which guess word best segments the remaining solution set.
        best_word = None
        best_score = -1

        # NOTE: If too slow, this can be sped up by restricting the potential_guesses and/or
        # potential_solutions iterations to a random sample.  This limits the iterations of this
        # O(nm) loop but does slightly decrease optimality.
        for word in self.potential_guesses:
            # Assuming we use this word as our guess, determine how the potential solutions will be grouped based on the obtained info.
            # For each potential solution, get the result string that would result from trying it, and count how many of each string in each group.
            solution_group_counts: dict[str, int] = {}
            for potsol in self.potential_solutions:
                resstr = self._fast_word_result(word, potsol)
                solution_group_counts[resstr] = solution_group_counts.get(resstr, 0) + 1
            # We want to optimize for smallest average expected group size.
            # The probability of the solution being in a given group is dependent on the group's size, so
            # the average expected group size is the weighted average of group sizes, weighted by group size.
            avg_expected_group_size = sum(( s * s for s in solution_group_counts.values() )) / sum(( s for s in solution_group_counts.values() ))
            word_score = avg_expected_group_size
            # Add a small boost if this word is one of the possible solutions
            if word in self.potential_solutions:
                word_score -= 0.01
            # Minimize the score
            if word_score < best_score or best_score == -1:
                best_score = word_score
                best_word = word

        return best_word

    @staticmethod
    def get_word_result(guess: str, target: str) -> str:
        """Returns the result string generated by comparing a guessed word to the correct target word."""
        r_list = [ 'X' ] * len(target)
        target_lcounts = WordleSolver._get_letter_counts(target, True)
        for i, (guess_letter, target_letter) in enumerate(zip(guess, target)):
            if guess_letter == target_letter:
                r_list[i] = 'C'
                target_lcounts[target_letter] -= 1
        for i, (guess_letter, target_letter) in enumerate(zip(guess, target)):
            if guess_letter != target_letter and target_lcounts[guess_letter] > 0:
                r_list[i] = 'L'
                target_lcounts[guess_letter] -= 1
        return ''.join(r_list)

    def run_auto(self, target_word: str) -> int:
        """Runs the game trying to guess a given target word.  Returns the number of guesses required."""
        self.reset()
        nguesses = 0
        while True:
            nguesses += 1
            guess = self.get_guess()
            if guess == target_word: break
            res = WordleSolver.get_word_result(guess, target_word)
            #print(f'Got guess {guess} ({res}) - Updating')
            self.update(guess, res)
        return nguesses


def run_interactive(solver):
    while True:
        guess = solver.get_guess()
        print('Guess: ' + guess)
        if len(solver.potential_solutions) == 1:
            print('That\'s the last possible solution in this dictionary.')
            return
        print('Enter feedback string using letters C, L, X.  Enter ! to blacklist word.  Or, to specify the word to guess: <word> <feedback>')
        res = input('Feedback (C/L/X = Correct position/Wrong position/Letter unused): ')
        # If input in form <word> <result>, then submit that word as the guess with the given result
        if re.fullmatch(r'[a-z]{' + str(solver.wordlen) + '} [CXL]{' + str(solver.wordlen) + '}', res):
            parts = res.split(' ')
            print(f'Guessed {parts[0]} with result {parts[1]}')
            solver.update(parts[0], parts[1])
        elif res == '!':
            print('Blacklisting word ' + guess)
            solver.potential_solutions.discard(guess)
            try:
                solver.all_solution_words.remove(guess)
            except ValueError:
                pass
            try:
                solver.all_guess_words.remove(guess)
            except ValueError:
                pass

            continue
        else:
            solver.update(guess, res)
        if solver.solved:
            return

def run_target(solver, target):
    nguesses = solver.run_auto(target)
    print(f'Guessed word {target} in {nguesses} guesses:')
    print('\n'.join(solver.tried_word_list))
    print(target)

def run_eval(solver):
    wlist = solver.all_solution_words.copy()
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
    nsuccess = nwords - len(failed_words)
    print(f'Successful words: {nsuccess}/{nwords} ({nsuccess/nwords*100}%)')


if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='Wordle Solver')
    argparser.add_argument('-i', action='store_true', help='Interactive solver mode')
    argparser.add_argument('-w', action='store', help='Solve target word mode')
    argparser.add_argument('-e', action='store_true', help='Evaluation/auto mode')
    argparser.add_argument('-H', action='store_true', help='Hard mode (only guess potential solutions)')
    args = argparser.parse_args()

    solver = WordleSolver(hard_mode=args.H)

    if args.i:
        assert(not args.e)
        assert(not args.w)
        run_interactive(solver)

    elif args.w:
        assert(not args.e)
        assert(isinstance(args.w, str))
        run_target(solver, args.w)

    elif args.e:
        run_eval(solver)

    else:
        raise Exception('Must supply one of -h, -i, -w <Target>, -e')



