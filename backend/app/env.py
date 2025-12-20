import gymnasium as gym
from gymnasium import spaces
import numpy as np
from baghchal.env import Board
from baghchal.lookup_table import action_space, reversed_action_space

class BaghChalEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array", "ansi"], "render_fps": 4}

    def __init__(self, render_mode=None):
        super().__init__()
        self.board = Board()
        self.action_space = spaces.Discrete(len(action_space))
        # 5x5x5 board representation as defined in baghchal.env.Board.board_repr
        # 0,1: piece positions (G, B)
        # 2: goats captured
        # 3: baghs trapped
        # 4: turn (1 if Goat)
        self.observation_space = spaces.Box(low=0, high=20, shape=(5, 5, 5), dtype=np.float64)
        self.render_mode = render_mode

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.board.reset()
        observation = self.board.board_repr()
        info = self._get_info()
        return observation, info

    def step(self, action):
        # Convert discrete action to move string
        move_str = reversed_action_space[action]
        
        # Check validity using the board's internal check or try/except
        # Note: baghchal library's validate raises Exception. 
        # But we can also check possible_moves_vector.
        
        # It's better to check if it's in possible moves to avoid exceptions and for RL safety
        # However, mapping string move back to the vector index is what action_space does.
        # So we can check if action is valid via mask.
        mask = self.board.possible_moves_vector()
        
        terminated = False
        truncated = False
        reward = 0
        
        if mask[action] == 0:
            # Invalid move
            # Strategies:
            # 1. End game with huge penalty
            # 2. Return negative reward and continue (but state didn't change)
            # 3. Random valid move (not good for pure RL)
            # Let's go with negative reward and continue, but typically masking is preferred.
            # For this simple env, I will treat invalid move as losing the turn or game?
            # Let's treat it as an immediate loss for simplicity in "strict" mode, 
            # or just -10 reward and no state change.
            reward = -10
            # To prevent infinite loops of invalid moves, we might want to truncate
            # but let's just return observation and hope the agent learns.
            # info = self._get_info()
            # return self.board.board_repr(), reward, terminated, truncated, info
            
            # Actually, standard is to terminate if we want to enforce rules strictly
            terminated = True
            reward = -100 # Heavy penalty
        else:
            # Valid move
            current_turn = self.board.next_turn
            try:
                # The move string from lookup table might be short "11" (placement) 
                # or long "1112" (move). baghchal env handles this via `pure_move` or `move`
                # pure_move adds the 'G' or 'B' prefix.
                
                # reversed_action_space gives raw coordinates e.g., '11' or '1112'
                # The `pure_move` method in Board handles adding the prefix based on turn.
                self.board.pure_move(move_str)
                
                # Check for win/loss
                if self.board.is_game_over():
                    terminated = True
                    winner = self.board.winner()
                    if winner == current_turn:
                        reward = 100
                    elif winner == "Draw": # specific check needed? board.winner returns 0 for draw?
                         reward = 0
                    else:
                        reward = -100
                        
            except Exception as e:
                # This should ideally not happen if mask[action] == 1
                print(f"Error executing move {move_str}: {e}")
                terminated = True
                reward = -100

        observation = self.board.board_repr()
        info = self._get_info()

        if self.render_mode == "human":
            self.render()

        return observation, reward, terminated, truncated, info

    def render(self):
        if self.render_mode == "ansi" or self.render_mode == "human":
            self.board.lightweight_show_board()
        elif self.render_mode == "rgb_array":
            # baghchal has a render method that uses PIL and shows image.
            # We can adapt it to return array.
            # For now, let's stick to simple text or implement PIL to array later if needed.
            pass

    def _get_info(self):
        return {
            "turn": self.board.next_turn,
            "action_mask": self.board.possible_moves_vector(),
            "pgn": self.board.pgn,
            "fen": self.board.fen
        }

    def close(self):
        pass
