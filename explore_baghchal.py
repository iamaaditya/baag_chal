from baghchal.env import Board

game = Board()
print(f"Turn: {game.next_turn}")
print(f"Board: {game.board}")
print(f"Goats placed: {game.goats_placed}")
print(f"Goats captured: {game.goats_captured}")
print(f"Game over: {game.is_game_over()}")
print(f"Moves: {list(game.possible_moves())}")
