from baghchal import Game

game = Game()
print(f"Turn: {game.turn()}")
print(f"Board: {game.board()}")
print(f"Goats placed: {game.goats_placed()}")
print(f"Goats captured: {game.goats_captured()}")
print(f"Game over: {game.is_game_over()}")
print(f"Moves: {game.moves()}")
