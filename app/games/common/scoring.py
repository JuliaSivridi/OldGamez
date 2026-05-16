def score_guess(secret: list, guess: list) -> tuple[int, int]:
    """Returns (bulls, cows) for any list-based guess vs secret."""
    bulls = sum(s == g for s, g in zip(secret, guess))
    secret_rest = [s for s, g in zip(secret, guess) if s != g]
    guess_rest = [g for s, g in zip(secret, guess) if s != g]
    cows = sum(min(secret_rest.count(x), guess_rest.count(x)) for x in set(guess_rest))
    return bulls, cows
