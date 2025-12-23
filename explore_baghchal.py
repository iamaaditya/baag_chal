from baghchal.env import Board

pgn_string = " 1. G33 B1122 2. G32 Bx2242 3. G23 Bx4224"
# Split into tokens: ['', '1.', 'G33', 'B1122', '2.', 'G32', 'Bx2242', '3.', 'G23', 'Bx4224']
tokens = pgn_string.strip().split()

# If we want move index 4 (Bx2242)
# The tokens up to 'Bx2242' are tokens[0:7]
# tokens[0] = '1.', tokens[1] = 'G33', tokens[2] = 'B1122', tokens[3] = '2.', tokens[4] = 'G32', tokens[5] = 'Bx2242'

# Let's try replaying up to move 4
# We need to find the K-th move (excluding move numbers)
moves_only = [t for t in tokens if not t.endswith('.')]
target_moves = moves_only[:4]

# Now we need a PGN string that contains these moves.
# The easiest way is to just take tokens until we have 4 moves.
count = 0
target_tokens = []
for t in tokens:
    target_tokens.append(t)
    if not t.endswith('.'):
        count += 1
    if count == 4:
        break

partial_pgn = " ".join(target_tokens)
print(f"Partial PGN for 4 moves: '{partial_pgn}'")

game = Board()
try:
    game.pgn_converter(partial_pgn)
    print(f"Moves made: {game.no_of_moves_made}")
    print(f"Success!")
except Exception as e:
    print(f"pgn_converter failed: {e}")
