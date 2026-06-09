"""
Main game file for

This script implements:
1. A Property class representing buyable spaces on the board.
2. An interactive popup triggering when landing on an unowned property.
3. Automatic rent transfer logic when landing on an opponent's property.
4. Scale-indexed rent mapping for Railroads ($25, $50, $100, $200).
5. Dynamic multiplier rent mapping for Utilities (4x or 10x dice sum).
"""

import sys
import random
import os
import json
import datetime
import pygame
import constants

# Static base rents lookup table for standard color-group properties
BASE_RENTS_DATA = {
    1: 2, 3: 4, 6: 6, 8: 6, 9: 8, 11: 10, 13: 10, 14: 12, 16: 14, 18: 14, 19: 16,
    21: 18, 23: 18, 24: 20, 26: 22, 27: 22, 29: 24, 31: 26, 32: 26, 34: 28, 37: 35, 39: 50
}

class Property:
    """
    Tracks state and financials for individual purchasable tiles on the board.
    """
    def __init__(self, index: int, name: str, price: int, base_rent: int, group: str):
        self.index = index
        self.name = name
        self.price = price
        self.base_rent = base_rent
        self.group = group
        self.owner = None  # Defaults to None (unowned)

class Player:
    """
    Represents a player in the Monopoly game.
    Encapsulates all personal attributes, cash trackers, and board position factors.
    """
    def __init__(self, player_id: int, name: str, color: tuple):
        self.player_id = player_id
        self.name = name
        self.color = color
        self.cash = constants.STARTING_CASH
        self.position = 0          # Tile index (0 to 39 around the board)
        self.is_in_jail = False
        self.jail_turns_count = 0
        
    def adjust_cash(self, amount: int) -> bool:
        """
        Safely modifies player's wallet balance.
        Returns False if the adjustment would bankrupt them (cash < 0), True otherwise.
        """
        if self.cash + amount < 0:
            return False
        self.cash += amount
        return True

    def move_position(self, steps: int) -> bool:
        """
        Advances the player along the board tile indices, wrapping at index 40.
        Returns True if the movement crossed or landed on GO (index 0), False otherwise.
        """
        old_pos = self.position
        new_pos = (old_pos + steps) % 40
        self.position = new_pos
        
        # Did we cross or land on GO? (0 <= new_pos < old_pos if moving forward)
        return new_pos < old_pos


class MonopolyGame:
    """
    Central Game Engine controlling window life cycles, input handlers, 
    view renderings, and core state transitions.
    """
    def __init__(self, num_players: int = 4):
        # Initialize pygame and window elements
        pygame.init()
        pygame.display.set_caption("Monopoly Simulator")
        self.screen = pygame.display.set_mode((1150, 800))
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Configure game fonts
        self.title_font = pygame.font.SysFont(constants.FONT_FAMILY, 24, bold=True)
        self.ui_font = pygame.font.SysFont(constants.FONT_FAMILY, 15, bold=True)
        self.sub_font = pygame.font.SysFont(constants.FONT_FAMILY, 13)
        self.code_font = pygame.font.SysFont("Courier", 13)
        self.tile_font = pygame.font.SysFont(constants.FONT_FAMILY, 9)
        self.tile_bold_font = pygame.font.SysFont(constants.FONT_FAMILY, 11, bold=True)
        self.tile_small_font = pygame.font.SysFont(constants.FONT_FAMILY, 8, bold=True)
        
        # Initialize Player list securely (2 to 8 players)
        self.num_players = max(constants.MIN_PLAYERS, min(num_players, constants.MAX_PLAYERS))
        self.players = []
        for i in range(self.num_players):
            name = f"Player {i + 1}"
            color = constants.PLAYER_COLORS[i]
            self.players.append(Player(player_id=i, name=name, color=color))
            
        # State trackers
        self.current_turn_index = 0
        self.dice1 = 1
        self.dice2 = 1
        self.roll_sum = 2
        self.has_rolled_this_turn = False
        
        # Launch screen state / game states
        self.game_started = False
        self.selected_player_count = 4 # Default selection
        self.player_buttons = {}
        for num in range(2, 9):
            x = 120 + (num - 2) * 80
            self.player_buttons[num] = pygame.Rect(x, 350, 60, 50)
            
        self.start_game_button_rect = pygame.Rect(300, 480, 200, 50)
        self.play_again_button_rect = pygame.Rect(300, 660, 200, 50)
        self.game_over = False
        
        # Save/Load states and overlay parameters
        self.start_screen_load_mode = False
        self.active_save_overlay = False
        
        # Save button displayed in board central region
        self.save_btn_rect = pygame.Rect(310, 575, 180, 42)
        
        # Overlay configurations for Save Game slots selection
        self.save_slot_rects = [
            pygame.Rect(250, 270, 300, 45),
            pygame.Rect(250, 330, 300, 45),
            pygame.Rect(250, 390, 300, 45)
        ]
        self.save_cancel_rect = pygame.Rect(325, 460, 150, 40)
        
        # Load Game launcher option on start page
        self.load_game_btn_rect = pygame.Rect(300, 550, 200, 50)
        
        # Load screen slots choices configurations
        self.load_slot_rects = [
            pygame.Rect(250, 280, 300, 60),
            pygame.Rect(250, 360, 300, 60),
            pygame.Rect(250, 440, 300, 60)
        ]
        self.load_cancel_rect = pygame.Rect(325, 520, 150, 40)
        
        # Activity log history list
        self.activity_log_history = []
        self.eliminated_players = []
        
        # Property class instances initialization
        self.properties = {}
        for idx, tile in enumerate(constants.TILES):
            if tile["group"] not in ["CORNER", "SPECIAL", "TAX"]:
                price = tile.get("price", 0)
                base_rent = BASE_RENTS_DATA.get(idx, 25 if tile["group"] == "RAILROAD" else 0)
                self.properties[idx] = Property(
                    index=idx,
                    name=tile["name"],
                    price=price,
                    base_rent=base_rent,
                    group=tile["group"]
                )
        
        # Interactive clickable button boundaries (600x600 board center space)
        self.roll_btn_rect = pygame.Rect(310, 360, 180, 42)
        self.pass_btn_rect = pygame.Rect(310, 415, 180, 42)
        self.end_btn_rect = pygame.Rect(310, 520, 180, 42)
        
        # Pop-up card YES / NO boundaries
        self.popup_yes_rect = pygame.Rect(260, 425, 120, 38)
        self.popup_no_rect = pygame.Rect(420, 425, 120, 38)
        
        # Jail Choice boundaries and Card Dismiss button boundaries
        self.jail_pay_rect = pygame.Rect(250, 370, 140, 38)
        self.jail_roll_rect = pygame.Rect(410, 370, 140, 38)
        self.jail_ok_rect = pygame.Rect(300, 410, 200, 38)
        self.card_ok_rect = pygame.Rect(330, 415, 140, 38)

        # Decks: Chance and Community Chest (Success Criteria 10)
        self.chance_cards = [
            {"text": "Advance to GO (Collect $200)", "type": "move", "target": 0},
            {"text": "Advance to Illinois Ave", "type": "move", "target": 24},
            {"text": "Advance to Boardwalk", "type": "move", "target": 39},
            {"text": "Bank pays you dividend of $50", "type": "money", "amount": 50},
            {"text": "Go Back 3 Spaces", "type": "move_back", "amount": 3},
            {"text": "Speeding fine $15", "type": "money", "amount": -15},
            {"text": "Pay poor tax of $15", "type": "money", "amount": -15},
            {"text": "Your building loan matures - Collect $150", "type": "money", "amount": 150}
        ]
        self.community_chest_cards = [
            {"text": "Advance to GO (Collect $200)", "type": "move", "target": 0},
            {"text": "Bank error in your favor - Collect $200", "type": "money", "amount": 200},
            {"text": "Doctor's fees - Pay $50", "type": "money", "amount": -50},
            {"text": "From sale of stock you get $50", "type": "money", "amount": 50},
            {"text": "Holiday fund matures - Receive $100", "type": "money", "amount": 100},
            {"text": "Income tax refund - Collect $20", "type": "money", "amount": 20},
            {"text": "School fees - Pay $150", "type": "money", "amount": -150},
            {"text": "Receive $25 services consultancy fee", "type": "money", "amount": 25}
        ]

        # Modal popup variables
        self.active_popup = None  # Property purchase card
        self.active_card_popup = None  # Action card card
        
        # Last event description text for the middle panel
        self.last_event_msg = "Game initialized. Click ROLL DICE to start."
        self.last_event_color = constants.COLOR_TEXT

    def get_current_player(self) -> Player:
        """
        Returns the Player instance whose turn is currently active.
        """
        return self.players[self.current_turn_index]

    def advance_turn(self):
        """
        Hands turn control over to the next player.
        """
        self.current_turn_index = (self.current_turn_index + 1) % len(self.players)
        self.has_rolled_this_turn = False
        self.log_action(f"{self.get_current_player().name}'s turn. Roll or Pass!", constants.COLOR_TEXT)

    def log_action(self, msg: str, color: tuple = constants.COLOR_TEXT):
        self.last_event_msg = msg
        self.last_event_color = color
        
        # Append to our activity log history (last 8 actions - Success Criteria 15)
        if not hasattr(self, 'activity_log_history'):
            self.activity_log_history = []
        self.activity_log_history.append((msg, color))
        if len(self.activity_log_history) > 8:
            self.activity_log_history.pop(0)

    def draw_text_left(self, surface, text, font, color, left_pos):
        """
        Helper method to render text aligned to the left side.
        """
        text_surf = font.render(text, True, color)
        rect = text_surf.get_rect(topleft=left_pos)
        surface.blit(text_surf, rect)

    def wrap_text_line(self, text, max_width_px):
        """
        Wraps long log text into multiple smaller lines before rendering.
        """
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            # estimate pixel length (~7.5 px per char)
            if len(test_line) * 7.5 > max_width_px:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)
        return lines

    def get_net_worth(self, player: Player) -> int:
        """
        Calculates player net worth as cash plus value of all owned properties.
        """
        total = player.cash
        for prop in self.properties.values():
            if prop.owner == player:
                total += prop.price
        return total

    def check_bankruptcy(self, player: Player) -> bool:
        """
        Triggers if player cash drops below $0. (Success Criteria 12)
        Liberates all owned properties back to None, removes active player, and triggers Game Over check.
        """
        if player.cash >= 0:
            return False
            
        print(f"[BANKRUPTCY] {player.name} went bankrupt with negative balance ${player.cash}!")
        self.log_action(f"❌ BANKRUPTCY: {player.name} is eliminated!", (239, 68, 68))
        
        # Reset property ownership
        for prop in self.properties.values():
            if prop.owner == player:
                prop.owner = None
                print(f"[BANKRUPTCY] Property {prop.name} reset to unowned.")
                
        # Register in eliminated list
        if not hasattr(self, 'eliminated_players'):
            self.eliminated_players = []
        if player not in self.eliminated_players:
            self.eliminated_players.append(player)
            
        # Remove from active list
        if player in self.players:
            self.players.remove(player)
            
        # Automatic game over check
        if len(self.players) <= 1:
            self.game_over = True
            return True
            
        # Align active turn indices
        self.current_turn_index = self.current_turn_index % len(self.players)
        self.has_rolled_this_turn = False
        self.log_action(f"{self.get_current_player().name}'s turn. Roll or Pass!", constants.COLOR_TEXT)
        return True

    def check_player_bankruptcy(self, player: Player) -> bool:
        if player.cash < 0:
            return self.check_bankruptcy(player)
        return False

    def setup_players(self, num_players: int):
        """
        Configures players list, resets all properties, logs settings, and starts game.
        """
        self.num_players = max(constants.MIN_PLAYERS, min(num_players, constants.MAX_PLAYERS))
        self.players = []
        for i in range(self.num_players):
            name = f"Player {i + 1}"
            color = constants.PLAYER_COLORS[i]
            p = Player(player_id=i, name=name, color=color)
            p.cash = 1500  # starting cash parameter - Success Criteria 1
            self.players.append(p)
            
        # Reset game variables
        self.current_turn_index = 0
        self.dice1 = 1
        self.dice2 = 1
        self.roll_sum = 2
        self.has_rolled_this_turn = False
        
        # Release all property ownerships
        for prop in self.properties.values():
            prop.owner = None
            
        # Clear tracker metrics
        self.active_popup = None
        self.active_card_popup = None
        self.eliminated_players = []
        self.game_over = False
        
        # Build logs
        self.activity_log_history = []
        self.log_action("Game Setup Complete!", constants.COLOR_TEXT)
        self.log_action(f"Configured with {self.num_players} players (Starting: $1500 each).", (99, 102, 241))
        
        # Open Board
        self.game_started = True

    def serialize_state(self) -> dict:
        """
        Gathers all required variables and objects to save the current progress of the simulation.
        """
        # Save active players list representation
        saved_players = []
        for p in self.players:
            saved_players.append({
                "player_id": p.player_id,
                "name": p.name,
                "color": list(p.color),
                "cash": p.cash,
                "position": p.position,
                "is_in_jail": p.is_in_jail,
                "jail_turns_count": p.jail_turns_count
            })
            
        # Save eliminated players list representation
        saved_eliminated = []
        for p in getattr(self, "eliminated_players", []):
            saved_eliminated.append({
                "player_id": p.player_id,
                "name": p.name,
                "color": list(p.color),
                "cash": p.cash,
                "position": p.position,
                "is_in_jail": p.is_in_jail,
                "jail_turns_count": p.jail_turns_count
            })
            
        # Save property ownership states mapped by index
        saved_properties = []
        for idx, prop in self.properties.items():
            saved_properties.append({
                "index": idx,
                "owner_id": prop.owner.player_id if prop.owner is not None else None
            })
            
        # Parse active card popup structure securely if exists
        saved_card_popup = None
        if self.active_card_popup:
            saved_card_popup = {
                "card": self.active_card_popup["card"],
                "deck_name": self.active_card_popup["deck_name"],
                "player_id": self.active_card_popup["player"].player_id
            }
            
        # Parse active buying popup structure if exists
        saved_buy_popup = None
        if self.active_popup:
            saved_buy_popup = {
                "property_index": self.active_popup["property"].index,
                "player_id": self.active_popup["player"].player_id
            }
            
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        
        state = {
            "num_players": self.num_players,
            "current_turn_index": self.current_turn_index,
            "dice1": self.dice1,
            "dice2": self.dice2,
            "roll_sum": self.roll_sum,
            "has_rolled_this_turn": self.has_rolled_this_turn,
            "game_started": self.game_started,
            "game_over": self.game_over,
            "last_event_msg": self.last_event_msg,
            "last_event_color": list(self.last_event_color) if isinstance(self.last_event_color, tuple) else self.last_event_color,
            "activity_log_history": [[item[0], list(item[1])] for item in getattr(self, "activity_log_history", [])],
            "players": saved_players,
            "eliminated_players": saved_eliminated,
            "properties": saved_properties,
            "active_card_popup": saved_card_popup,
            "active_popup": saved_buy_popup,
            "timestamp": timestamp
        }
        return state

    def deserialize_state(self, state: dict):
        """
        Reconstructs the MonopolyGame environment perfectly from a state dictionary.
        """
        # Restore simple variables first
        self.num_players = state["num_players"]
        self.current_turn_index = state["current_turn_index"]
        self.dice1 = state["dice1"]
        self.dice2 = state["dice2"]
        self.roll_sum = state["roll_sum"]
        self.has_rolled_this_turn = state["has_rolled_this_turn"]
        self.game_started = state["game_started"]
        self.game_over = state["game_over"]
        self.last_event_msg = state["last_event_msg"]
        
        # Color helper parser
        col = state["last_event_color"]
        self.last_event_color = tuple(col) if isinstance(col, list) else col
        
        # Restore full histories logs
        self.activity_log_history = []
        for text, color_list in state.get("activity_log_history", []):
            self.activity_log_history.append((text, tuple(color_list)))
            
        # Restore Player rosters
        self.players = []
        for p_data in state["players"]:
            p = Player(player_id=p_data["player_id"], name=p_data["name"], color=tuple(p_data["color"]))
            p.cash = p_data["cash"]
            p.position = p_data["position"]
            p.is_in_jail = p_data["is_in_jail"]
            p.jail_turns_count = p_data["jail_turns_count"]
            self.players.append(p)
            
        self.eliminated_players = []
        for p_data in state.get("eliminated_players", []):
            p = Player(player_id=p_data["player_id"], name=p_data["name"], color=tuple(p_data["color"]))
            p.cash = p_data["cash"]
            p.position = p_data["position"]
            p.is_in_jail = p_data["is_in_jail"]
            p.jail_turns_count = p_data["jail_turns_count"]
            self.eliminated_players.append(p)
            
        # Build quick player reference index map
        all_players_by_id = {p.player_id: p for p in self.players + self.eliminated_players}
        
        # Restore property ownerships
        for prop in self.properties.values():
            prop.owner = None
            
        for prop_state in state["properties"]:
            idx = prop_state["index"]
            owner_id = prop_state["owner_id"]
            if idx in self.properties:
                if owner_id is not None:
                    self.properties[idx].owner = all_players_by_id.get(owner_id)
                else:
                    self.properties[idx].owner = None
                    
        # Re-initialize modals / overlay popups
        saved_card_popup = state.get("active_card_popup")
        if saved_card_popup:
            self.active_card_popup = {
                "card": saved_card_popup["card"],
                "deck_name": saved_card_popup["deck_name"],
                "player": all_players_by_id.get(saved_card_popup["player_id"])
            }
        else:
            self.active_card_popup = None
            
        saved_buy_popup = state.get("active_popup")
        if saved_buy_popup:
            self.active_popup = {
                "property": self.properties.get(saved_buy_popup["property_index"]),
                "player": all_players_by_id.get(saved_buy_popup["player_id"])
            }
        else:
            self.active_popup = None

    def save_current_game(self, slot_num: int):
        """
        Serializes current Monopoly game state to a JSON file corresponding to slot_num.
        """
        filename = f"save_slot_{slot_num}.json"
        try:
            state = self.serialize_state()
            with open(filename, "w") as f:
                json.dump(state, f, indent=4)
            self.log_action(f"💾 Game successfully saved to Slot {slot_num}!", (16, 185, 129))
            print(f"[SYSTEM] Game saved to {filename}")
        except Exception as e:
            self.log_action(f"❌ Error saving to Slot {slot_num}!", (239, 68, 68))
            print(f"[SYSTEM] Error saving game: {e}")

    def load_saved_game(self, slot_num: int) -> bool:
        """
        Loads and deserializes game state from JSON file corresponding to slot_num.
        """
        filename = f"save_slot_{slot_num}.json"
        if not os.path.exists(filename):
            print(f"[SYSTEM] Cannot load; {filename} does not exist.")
            return False
        try:
            with open(filename, "r") as f:
                state = json.load(f)
            self.deserialize_state(state)
            self.log_action(f"💾 Game loaded from Slot {slot_num}!", (16, 185, 129))
            print(f"[SYSTEM] Game loaded from {filename}")
            return True
        except Exception as e:
            print(f"[SYSTEM] Error loading game: {e}")
            return False

    def draw_start_screen(self):
        if getattr(self, "start_screen_load_mode", False):
            self.draw_load_screen()
            return
            
        self.screen.fill((15, 23, 42)) # Slate 900 background
        
        # Center grid content frame
        pygame.draw.rect(self.screen, (30, 41, 59), (50, 50, 700, 700), border_radius=15)
        pygame.draw.rect(self.screen, (74, 85, 104), (50, 50, 700, 700), 3, border_radius=15)
        
        self.draw_text_centered(
            self.screen,
            "★ MONOPOLY SIMULATOR ★",
            pygame.font.SysFont(constants.FONT_FAMILY, 36, bold=True),
            (99, 102, 241),
            (400, 150)
        )
        self.draw_text_centered(
            self.screen,
            "Interactive Local Multiplayer Board Game",
            self.sub_font,
            (148, 163, 184),
            (400, 210)
        )
        
        self.draw_text_centered(
            self.screen,
            "SELECT NUMBER OF HUMAN PLAYERS:",
            self.ui_font,
            constants.COLOR_WHITE,
            (400, 300)
        )
        
        # Draw player choosing circles
        mouse_pos = pygame.mouse.get_pos()
        for num, rect in self.player_buttons.items():
            is_hover = rect.collidepoint(mouse_pos)
            is_selected = (num == self.selected_player_count)
            
            if is_selected:
                bg_color = (99, 102, 241)
                text_color = constants.COLOR_WHITE
                border_color = constants.COLOR_WHITE
            elif is_hover:
                bg_color = (51, 65, 85)
                text_color = (226, 232, 240)
                border_color = (99, 102, 241)
            else:
                bg_color = (30, 41, 59)
                text_color = (148, 163, 184)
                border_color = (71, 85, 105)
                
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=8)
            self.draw_text_centered(self.screen, f"{num}P", self.ui_font, text_color, rect.center)
            
        # Draw Launch button
        is_launch_hover = self.start_game_button_rect.collidepoint(mouse_pos)
        launch_bg = (16, 185, 129) if is_launch_hover else (5, 150, 105)
        pygame.draw.rect(self.screen, launch_bg, self.start_game_button_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_WHITE, self.start_game_button_rect, 2, border_radius=8)
        self.draw_text_centered(self.screen, "LAUNCH SIMULATION", self.ui_font, constants.COLOR_WHITE, self.start_game_button_rect.center)
        
        # Draw Load Game button
        is_load_hover = self.load_game_btn_rect.collidepoint(mouse_pos)
        load_bg = (99, 102, 241) if is_load_hover else (67, 56, 202)
        pygame.draw.rect(self.screen, load_bg, self.load_game_btn_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_WHITE, self.load_game_btn_rect, 2, border_radius=8)
        self.draw_text_centered(self.screen, "LOAD GAME", self.ui_font, constants.COLOR_WHITE, self.load_game_btn_rect.center)
        
        # Clean silent sidebar
        preview_rect = pygame.Rect(800, 0, 350, 800)
        pygame.draw.rect(self.screen, (15, 23, 42), preview_rect)
        pygame.draw.line(self.screen, (47, 55, 71), (800, 0), (800, 800), 3)

    def draw_load_screen(self):
        self.screen.fill((15, 23, 42)) # Slate 900 background
        
        # Center grid content frame
        pygame.draw.rect(self.screen, (30, 41, 59), (50, 50, 700, 700), border_radius=15)
        pygame.draw.rect(self.screen, (74, 85, 104), (50, 50, 700, 700), 3, border_radius=15)
        
        self.draw_text_centered(
            self.screen,
            "★ LOAD SAVED GAME ★",
            pygame.font.SysFont(constants.FONT_FAMILY, 36, bold=True),
            (99, 102, 241),
            (400, 150)
        )
        self.draw_text_centered(
            self.screen,
            "Select a slot below to restore your match progress",
            self.sub_font,
            (148, 163, 184),
            (400, 210)
        )
        
        mouse_pos = pygame.mouse.get_pos()
        
        # Render slot choices
        for idx, rect in enumerate(self.load_slot_rects):
            slot_num = idx + 1
            filename = f"save_slot_{slot_num}.json"
            is_hover = rect.collidepoint(mouse_pos)
            
            slot_exists = os.path.exists(filename)
            slot_desc1 = f"Slot {slot_num}: [ Empty Slot ]"
            slot_desc2 = "No saved session data found"
            
            if slot_exists:
                try:
                    with open(filename, "r") as f:
                        data = json.load(f)
                    timestamp = data.get("timestamp", "Unknown Date")
                    turn_idx = data.get("current_turn_index", 0)
                    players_list = data.get("players", [])
                    active_p_name = players_list[turn_idx].get("name", "Unknown Player") if turn_idx < len(players_list) else "Unknown"
                    slot_desc1 = f"Slot {slot_num}: {len(players_list)} Players - {active_p_name}'s Turn"
                    slot_desc2 = f"Saved on: {timestamp}"
                except:
                    slot_desc1 = f"Slot {slot_num}: [ Corrupted Data ]"
                    slot_desc2 = "Failed to load state schema safely"
                    
            if slot_exists:
                bg_color = (16, 185, 129) if is_hover else (4, 120, 87)
                border_color = constants.COLOR_WHITE if is_hover else (16, 185, 129)
                text_color = constants.COLOR_WHITE
            else:
                bg_color = (51, 65, 85) if is_hover else (30, 41, 59)
                border_color = (99, 102, 241) if is_hover else (71, 85, 105)
                text_color = (148, 163, 184)
                
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=8)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=8)
            
            self.draw_text_centered(self.screen, slot_desc1, self.ui_font, text_color, (rect.centerx, rect.centery - 10))
            self.draw_text_centered(self.screen, slot_desc2, self.sub_font, text_color, (rect.centerx, rect.centery + 12))
            
        # Cancel Button
        is_cancel_hover = self.load_cancel_rect.collidepoint(mouse_pos)
        cancel_bg = (239, 68, 68) if is_cancel_hover else (185, 28, 28)
        pygame.draw.rect(self.screen, cancel_bg, self.load_cancel_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_WHITE, self.load_cancel_rect, 2, border_radius=8)
        self.draw_text_centered(self.screen, "CANCEL", self.ui_font, constants.COLOR_WHITE, self.load_cancel_rect.center)
        
        # Clean silent sidebar
        preview_rect = pygame.Rect(800, 0, 350, 800)
        pygame.draw.rect(self.screen, (15, 23, 42), preview_rect)
        pygame.draw.line(self.screen, (47, 55, 71), (800, 0), (800, 800), 3)

    def draw_game_over_screen(self):
        self.screen.fill((15, 23, 42))
        
        # Standings inner cage
        pygame.draw.rect(self.screen, (30, 41, 59), (50, 50, 700, 700), border_radius=15)
        pygame.draw.rect(self.screen, (74, 85, 104), (50, 50, 700, 700), 3, border_radius=15)
        
        self.draw_text_centered(
            self.screen,
            "★ GAME OVER ★",
            pygame.font.SysFont(constants.FONT_FAMILY, 38, bold=True),
            (239, 68, 68),
            (400, 150)
        )
        
        winners = []
        winner_net_worth = 0
        if len(self.players) >= 1:
            # Find maximum net worth among active players
            max_nw = max(self.get_net_worth(p) for p in self.players)
            winners = [p for p in self.players if self.get_net_worth(p) == max_nw]
            winner_net_worth = max_nw
            
            if len(winners) > 1:
                winner_names = ", ".join(w.name for w in winners)
                winner_text = f"🏆 TIE FOR 1ST: {winner_names}! 🏆"
                winner_col = (234, 179, 8) # Golden Yellow for the tie
            else:
                winner_text = f"🏆 WINNER: {winners[0].name}! 🏆"
                winner_col = winners[0].color
        else:
            winner_text = "GAME OVER"
            winner_col = constants.COLOR_WHITE
            winner_net_worth = 0
            
        if len(winners) >= 1:
            self.draw_text_centered(
                self.screen,
                winner_text,
                pygame.font.SysFont(constants.FONT_FAMILY, 24, bold=True),
                winner_col,
                (400, 225)
            )
            self.draw_text_centered(
                self.screen,
                f"FINAL NET WORTH: ${winner_net_worth:,}",
                self.ui_font,
                (16, 185, 129),
                (400, 265)
            )
            
        # Standings list header
        self.draw_text_centered(
            self.screen,
            "--- STANDINGS AND RANKINGS ---",
            self.ui_font,
            (148, 163, 184),
            (400, 335)
        )
        
        # Fetch standings
        all_players = list(self.players) + list(getattr(self, 'eliminated_players', []))
        all_players.sort(key=lambda p: self.get_net_worth(p), reverse=True)
        
        current_rank = 1
        for idx, p in enumerate(all_players):
            if idx > 0:
                prev_p = all_players[idx - 1]
                if self.get_net_worth(p) != self.get_net_worth(prev_p):
                    current_rank = idx + 1
            else:
                current_rank = 1
                
            nw = self.get_net_worth(p)
            status_desc = f"${nw:,}"
            if p in getattr(self, 'eliminated_players', []):
                status_desc += " (ELIMINATED)"
                
            y = 370 + idx * 30
            text_line = f"Rank {current_rank}: {p.name}  -  Net Worth: {status_desc}"
            text_color = p.color if p not in getattr(self, 'eliminated_players', []) else (100, 116, 139)
            self.draw_text_centered(self.screen, text_line, self.sub_font, text_color, (400, y))
            
        # PLAY AGAIN button
        mouse_pos = pygame.mouse.get_pos()
        is_play_again_hover = self.play_again_button_rect.collidepoint(mouse_pos)
        btn_bg = (16, 185, 129) if is_play_again_hover else (5, 150, 105)
        pygame.draw.rect(self.screen, btn_bg, self.play_again_button_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_WHITE, self.play_again_button_rect, 2, border_radius=8)
        self.draw_text_centered(self.screen, "PLAY AGAIN", self.ui_font, constants.COLOR_WHITE, self.play_again_button_rect.center)
        
        # Clean silent sidebar
        preview_rect = pygame.Rect(800, 0, 350, 800)
        pygame.draw.rect(self.screen, (15, 23, 42), preview_rect)
        pygame.draw.line(self.screen, (47, 55, 71), (800, 0), (800, 800), 3)

    def calculate_rent(self, prop: Property, owner: Player, dice_sum: int) -> int:
        """
        Calculates the rent due based on property type, count owned, and dice outcomes.
        """
        if prop.group == "RAILROAD":
            # Count railroads owned by this owner
            count = sum(1 for p in self.properties.values() if p.group == "RAILROAD" and p.owner == owner)
            railroad_rents = {1: 25, 2: 50, 3: 100, 4: 200}
            return railroad_rents.get(count, 25)
            
        elif prop.group == "UTILITY":
            # Count utilities owned by owner
            count = sum(1 for p in self.properties.values() if p.group == "UTILITY" and p.owner == owner)
            multiplier = 4 if count == 1 else 10
            return multiplier * dice_sum
            
        else:
            return prop.base_rent

    def resolve_buy_popup(self, buy: bool):
        """
        Process unowned property decision: buyers cash is validated and owner token assigned on YES.
        """
        if not self.active_popup:
            return
            
        prop = self.active_popup["property"]
        player = self.active_popup["player"]
        
        if buy:
            if player.cash >= prop.price:
                player.adjust_cash(-prop.price)
                prop.owner = player
                self.log_action(f"{player.name} bought {prop.name} for ${prop.price}!", (0, 150, 0))
                print(f"[BUY] {player.name} bought {prop.name} for ${prop.price}.")
                self.active_popup = None
            else:
                self.log_action(f"Insufficient Funds! {player.name} needs ${prop.price} (Have: ${player.cash}).", (200, 50, 50))
                # Keep active_popup open so they must Decline or gain funds
        else:
            self.log_action(f"{player.name} declined to buy {prop.name}.", constants.COLOR_TEXT)
            print(f"[DECLINE] {player.name} declined to buy {prop.name}.")
            self.active_popup = None

    def resolve_space_landing(self, active_player: Player, new_pos: int, passed_go: bool, dice_sum: int):
        """
        Processes landing rules for properties, taxes, Special (Chance/CC), and Go To Jail.
        Handles nested recursive teleporting if a drawn card shifts position.
        """
        go_bonus_applied = False
        if passed_go or new_pos == 0:
            active_player.adjust_cash(200)
            go_bonus_applied = True
            print(f"[GAME ENGINE] Passed GO! Credited $200. {active_player.name} wallet: ${active_player.cash}")

        # 1. Landing exactly on GO TO JAIL (index 30 - Success Criteria 9)
        if new_pos == 30:
            active_player.position = 10
            active_player.is_in_jail = True
            active_player.jail_turns_count = 0
            self.log_action(f"🚔 {active_player.name} landed on GO TO JAIL! Sent directly to Jail.", (200, 30, 30))
            print(f"[JAIL] {active_player.name} sent directly to Jail index 10.")
            self.has_rolled_this_turn = True  # Locks roll
            return

        # 2. Taxes coordinates check (Income Tax = index 4, Luxury Tax = index 38)
        tax_cost = 0
        tax_name = ""
        if new_pos == 4:
            tax_cost = 200
            tax_name = "Income Tax"
            active_player.adjust_cash(-tax_cost)
            print(f"[TAX] {active_player.name} paid {tax_name} of ${tax_cost}.")
        elif new_pos == 38:
            tax_cost = 100
            tax_name = "Luxury Tax"
            active_player.adjust_cash(-tax_cost)
            print(f"[TAX] {active_player.name} paid {tax_name} of ${tax_cost}.")

        msg = f"{active_player.name} landed on {constants.TILES[new_pos]['name']}."
        if go_bonus_applied:
            msg += " Passed GO (+$200)!"
        if tax_cost > 0:
            msg += f" Paid {tax_name} (-${tax_cost})!"
            self.log_action(msg, (200, 50, 50))
            self.check_player_bankruptcy(active_player)
            return

        # 3. Action Cards space triggers (Chance indices: 7, 22, 36 | Community Chest: 2, 17, 33)
        # Success Criteria 10 & 11
        if new_pos in [7, 22, 36]:
            card = random.choice(self.chance_cards)
            self.active_card_popup = {"card": card, "deck_name": "Chance", "player": active_player}
            self.log_action(f"Chance Box! {active_player.name} draws telegram...", (197, 17, 98))
            print(f"[CARD DRAW] Chance: {card['text']}")
            return
        elif new_pos in [2, 17, 33]:
            card = random.choice(self.community_chest_cards)
            self.active_card_popup = {"card": card, "deck_name": "Community Chest", "player": active_player}
            self.log_action(f"Chest Box! {active_player.name} draws telegram...", (32, 201, 151))
            print(f"[CARD DRAW] Community Chest: {card['text']}")
            return

        # 4. Color-group properties/utilities/railroads resolution
        # Success Criteria 5, 6, 7, 8
        prop = self.properties.get(new_pos)
        if prop:
            if prop.owner is None:
                # Trigger purchase decision popup (Success Criteria 5)
                self.active_popup = {"property": prop, "player": active_player}
                msg += f" Landed on unowned {prop.name} (${prop.price})."
                self.log_action(msg, (0, 110, 220))
            elif prop.owner != active_player:
                # Rent Transfer (Success Criteria 6)
                rent_due = self.calculate_rent(prop, prop.owner, dice_sum)
                active_player.adjust_cash(-rent_due)
                prop.owner.adjust_cash(rent_due)
                msg += f" Paid ${rent_due} rent to {prop.owner.name}!"
                self.log_action(msg, (180, 10, 10))
                print(f"[RENT_TRANSFER] {active_player.name} paid ${rent_due} rent to {prop.owner.name} (on {prop.name}).")
                self.check_player_bankruptcy(active_player)
            else:
                msg += f" Landed on your own property: {prop.name}."
                self.log_action(msg, (0, 120, 0))
        else:
            col = (0, 120, 0) if go_bonus_applied else constants.COLOR_TEXT
            self.log_action(msg, col)

    def execute_card_effect(self, player: Player, card: dict):
        """
        Applies card transactions and triggers recursive landing resolutions instantly upon card dismissal.
        """
        if card["type"] == "money":
            player.adjust_cash(card["amount"])
            amt_text = f"+${card['amount']}" if card['amount'] > 0 else f"-${abs(card['amount'])}"
            self.log_action(f"{player.name} resolved Card: {amt_text}!", (0, 120, 0) if card['amount'] > 0 else (180, 10, 10))
            print(f"[CARD RESOLVE] Money effect: {amt_text}. New balance: ${player.cash}")
            self.check_player_bankruptcy(player)
        elif card["type"] == "move":
            old_pos = player.position
            target_pos = card["target"]
            player.position = target_pos
            
            # Cross or land on GO checks
            passed_go = target_pos < old_pos or target_pos == 0
            print(f"[CARD RESOLVE] Telegram to {constants.TILES[target_pos]['name']} (Passed GO? {passed_go})")
            
            # Recursively land on target space!
            self.resolve_space_landing(player, target_pos, passed_go, self.roll_sum)
        elif card["type"] == "move_back":
            old_pos = player.position
            target_pos = (old_pos - card["amount"]) % 40
            player.position = target_pos
            print(f"[CARD RESOLVE] Go Back {card['amount']} to {constants.TILES[target_pos]['name']}")
            
            # Backwards movement doesn't cross GO
            self.resolve_space_landing(player, target_pos, False, self.roll_sum)

    def resolve_jail_choice(self, pay: bool):
        """
        Handles interactive Jail decisions (Option A = Pay $50, Option B = Roll Doubles coefficients).
        Success Criteria 9.
        """
        player = self.get_current_player()
        if not player.is_in_jail:
            return

        if pay:
            # Deduct escape fee
            player.adjust_cash(-50)
            player.is_in_jail = False
            player.jail_turns_count = 0
            self.log_action(f"🔓 {player.name} paid $50 to leave Jail! Roll normally now.", (0, 150, 0))
            print(f"[JAIL] {player.name} paid $50 to escape Jail.")
            self.check_player_bankruptcy(player)
            # We do NOT set has_rolled_this_turn so they can click the normal roll button immediately!
        else:
            # Roll for doubles
            self.dice1 = random.randint(1, 6)
            self.dice2 = random.randint(1, 6)
            self.roll_sum = self.dice1 + self.dice2
            self.has_rolled_this_turn = True # Consumes roll turn state
            
            print(f"[JAIL ROLL] {player.name} rolled for Doubles: {self.dice1} vs {self.dice2}")
            
            if self.dice1 == self.dice2:
                # Doubles rolled! Free escape
                player.is_in_jail = False
                player.jail_turns_count = 0
                self.log_action(f"🎲 DOUBLES! Rolled {self.dice1}s. {player.name} escaped for free, moving {self.roll_sum}!", (0, 150, 0))
                print(f"[JAIL] {player.name} rolled Doubles and escaped.")
                
                passed_go = player.move_position(self.roll_sum)
                self.resolve_space_landing(player, player.position, passed_go, self.roll_sum)
            else:
                # Fails roll
                player.jail_turns_count += 1
                self.log_action(f"Failed! Rolled {self.dice1}+{self.dice2}. {player.name} remains in Jail ({player.jail_turns_count}/3).", (180, 10, 10))
                print(f"[JAIL] Failed doubles. Remains in Jail (Failed: {player.jail_turns_count}/3).")

    def resolve_forced_jail_pay(self):
        """
        Demands mandatory payment of $50 when player starts 3rd turn in Jail.
        """
        player = self.get_current_player()
        player.adjust_cash(-50)
        player.is_in_jail = False
        player.jail_turns_count = 0
        self.log_action(f"🚔 {player.name} paid $50 mandatory fine to leave Jail (3 turns failed). Released.", (0, 150, 0))
        print(f"[JAIL] {player.name} forced pay $50.")
        # Can roll normally immediately
        self.has_rolled_this_turn = False
        self.check_player_bankruptcy(player)

    def execute_roll_movement(self):
        """
        Primary movement trigger: rolls two dice, adjusts active position,
        handles jail escape check, and triggers landing resolutions.
        """
        active_player = self.get_current_player()
        
        # Verify Jail status before letting them roll normally
        if active_player.is_in_jail:
            self.log_action("Imprisoned in Jail! Must resolve bail option first.", (180, 10, 10))
            return

        # 1. Roll 2 dice
        self.dice1 = random.randint(1, 6)
        self.dice2 = random.randint(1, 6)
        self.roll_sum = self.dice1 + self.dice2
        self.has_rolled_this_turn = True
        
        self.log_action(f"🎲 {active_player.name} rolled {self.dice1} + {self.dice2} = {self.roll_sum}!", (0, 100, 200))
        print(f"[TEST RUN] {active_player.name} rolled: {self.dice1} + {self.dice2} = {self.roll_sum}")
        
        # 2. Track old and calculate movement
        passed_go = active_player.move_position(self.roll_sum)
        new_pos = active_player.position
        
        # 3. Handle recursive resolutions based on landing tile
        self.resolve_space_landing(active_player, new_pos, passed_go, self.roll_sum)

    def handle_events(self):
        """
        Scans mouse clicking triggers and keyboard inputs.
        """
        # If launch screen is visible (Success Criteria 1)
        if not self.game_started:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = event.pos
                    
                    if getattr(self, "start_screen_load_mode", False):
                        # Handle Load screen clicks
                        if self.load_cancel_rect.collidepoint(mouse_pos):
                            self.start_screen_load_mode = False
                        else:
                            for idx, rect in enumerate(self.load_slot_rects):
                                if rect.collidepoint(mouse_pos):
                                    filename = f"save_slot_{idx+1}.json"
                                    if os.path.exists(filename):
                                        success = self.load_saved_game(idx+1)
                                        if success:
                                            self.start_screen_load_mode = False
                        continue
                        
                    # Check player count selection buttons
                    for num, rect in self.player_buttons.items():
                        if rect.collidepoint(mouse_pos):
                            self.selected_player_count = num
                            print(f"[LAUNCH SCREEN] Player count selected: {num}")
                    # Check Start Game button
                    if self.start_game_button_rect.collidepoint(mouse_pos):
                        self.setup_players(self.selected_player_count)
                    # Check Load Game option
                    elif self.load_game_btn_rect.collidepoint(mouse_pos):
                        self.start_screen_load_mode = True
            return

        # If game is over
        if self.game_over:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = event.pos
                    if self.play_again_button_rect.collidepoint(mouse_pos):
                        self.game_started = False
                        self.game_over = False
            return

        active_p = self.get_current_player()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    mouse_pos = event.pos
                    
                    # Check manual END GAME button first (so it works during any popup too!)
                    if self.end_btn_rect.collidepoint(mouse_pos):
                        self.game_over = True
                        self.log_action("Game ended manually by players.", (239, 68, 68))
                        print("[EVENT] Game manually ended.")
                        continue
                        
                    # Handle active Save Popup overlay first
                    if getattr(self, "active_save_overlay", False):
                        if self.save_cancel_rect.collidepoint(mouse_pos):
                            self.active_save_overlay = False
                        else:
                            for idx, rect in enumerate(self.save_slot_rects):
                                if rect.collidepoint(mouse_pos):
                                    self.save_current_game(idx + 1)
                                    self.active_save_overlay = False
                        continue
                        
                    # Check manual SAVE GAME button (open Save options layout)
                    if self.save_btn_rect.collidepoint(mouse_pos):
                        self.active_save_overlay = True
                        continue
                    
                    # 1. Restrict clicks if active Card Popup is showing
                    if self.active_card_popup:
                        if self.card_ok_rect.collidepoint(mouse_pos):
                            # Process card effects on dismiss
                            card = self.active_card_popup["card"]
                            player = self.active_card_popup["player"]
                            self.active_card_popup = None
                            self.execute_card_effect(player, card)
                        continue

                    # 2. Restrict clicks if Buy Property Modal is showing
                    if self.active_popup:
                        if self.popup_yes_rect.collidepoint(mouse_pos):
                            self.resolve_buy_popup(True)
                        elif self.popup_no_rect.collidepoint(mouse_pos):
                            self.resolve_buy_popup(False)
                        continue
                    
                    # 3. Restrict clicks if Jail popup is showing
                    if active_p.is_in_jail and not self.has_rolled_this_turn:
                        if active_p.jail_turns_count >= 3:
                            if self.jail_ok_rect.collidepoint(mouse_pos):
                                self.resolve_forced_jail_pay()
                        else:
                            if self.jail_pay_rect.collidepoint(mouse_pos):
                                self.resolve_jail_choice(True)
                            elif self.jail_roll_rect.collidepoint(mouse_pos):
                                self.resolve_jail_choice(False)
                        continue

                    # Detect click on ROLL DICE button
                    if self.roll_btn_rect.collidepoint(mouse_pos):
                        if not self.has_rolled_this_turn:
                            self.execute_roll_movement()
                        else:
                            self.log_action("Already rolled! Click PASS TURN first.", (180, 100, 0))
                            
                    # Detect click on PASS TURN button
                    elif self.pass_btn_rect.collidepoint(mouse_pos):
                        # Block PASS turn click if pass is blocked (Success Criteria 2)
                        is_pass_blocked = (
                            not self.has_rolled_this_turn or
                            self.active_popup is not None or 
                            self.active_card_popup is not None or 
                            (active_p.is_in_jail and not self.has_rolled_this_turn)
                        )
                        if not is_pass_blocked:
                            self.advance_turn()
                        else:
                            self.log_action("Roll dice first before passing your turn!", (200, 50, 50))
                        
            elif event.type == pygame.KEYDOWN:
                # 0. Restrict keyboard if active Save Popup is showing
                if getattr(self, "active_save_overlay", False):
                    if event.key == pygame.K_ESCAPE:
                        self.active_save_overlay = False
                    continue
                    
                # 1. Restrict keyboard if active Card Popup is showing
                if self.active_card_popup:
                    if event.key in [pygame.K_space, pygame.K_RETURN, pygame.K_ESCAPE]:
                        card = self.active_card_popup["card"]
                        player = self.active_card_popup["player"]
                        self.active_card_popup = None
                        self.execute_card_effect(player, card)
                    continue

                # 2. Restrict keyboard if Buy Property Modal is showing
                if self.active_popup:
                    if event.key == pygame.K_y:
                        self.resolve_buy_popup(True)
                    elif event.key in [pygame.K_n, pygame.K_ESCAPE]:
                        self.resolve_buy_popup(False)
                    continue
                    
                # 3. Restrict keyboard if Jail choice is showing
                if active_p.is_in_jail and not self.has_rolled_this_turn:
                    if active_p.jail_turns_count >= 3:
                        if event.key in [pygame.K_SPACE, pygame.K_RETURN, pygame.K_p]:
                            self.resolve_forced_jail_pay()
                    else:
                        if event.key == pygame.K_p: # Pay $50
                            self.resolve_jail_choice(True)
                        elif event.key == pygame.K_r: # Roll Doubles
                            self.resolve_jail_choice(False)
                    continue

                # Standard shortcuts
                if event.key == pygame.K_SPACE:
                    if not self.has_rolled_this_turn:
                        self.execute_roll_movement()
                    else:
                        is_pass_blocked = (
                            not self.has_rolled_this_turn or
                            self.active_popup is not None or 
                            self.active_card_popup is not None or 
                            (active_p.is_in_jail and not self.has_rolled_this_turn)
                        )
                        if not is_pass_blocked:
                            self.advance_turn()
                        
                elif event.key == pygame.K_RETURN:
                    is_pass_blocked = (
                        not self.has_rolled_this_turn or
                        self.active_popup is not None or 
                        self.active_card_popup is not None or 
                        (active_p.is_in_jail and not self.has_rolled_this_turn)
                    )
                    if not is_pass_blocked:
                        self.advance_turn()
                        print(f"[TEST RUN] Moved turn. Active: {self.get_current_player().name}")
                    else:
                        self.log_action("Roll dice first before passing your turn!", (200, 50, 50))
                    
                elif event.key == pygame.K_UP:
                    active = self.get_current_player()
                    active.adjust_cash(200)
                    self.log_action(f"Manual Credit +$200 to {active.name}", (0, 110, 0))
                    
                elif event.key == pygame.K_DOWN:
                    active = self.get_current_player()
                    active.adjust_cash(-150)
                    self.log_action(f"Manual Tax Deduction -$150 from {active.name}", (180, 10, 10))
                    self.check_player_bankruptcy(active)

    def get_tile_rect(self, index: int) -> pygame.Rect:
        """
        Calculates the screen pygame.Rect for a given board tile index (0 to 39).
        """
        board_size = constants.BOARD_SIZE
        corner_size = constants.CORNER_SIZE
        side_span = board_size - 2 * corner_size # 600
        step = side_span / 9.0
        
        if index == 0:
            return pygame.Rect(board_size - corner_size, board_size - corner_size, corner_size, corner_size)
        elif index == 10:
            return pygame.Rect(0, board_size - corner_size, corner_size, corner_size)
        elif index == 20:
            return pygame.Rect(0, 0, corner_size, corner_size)
        elif index == 30:
            return pygame.Rect(board_size - corner_size, 0, corner_size, corner_size)
            
        if 0 < index < 10:
            x_start = int(round(board_size - corner_size - index * step))
            x_end = int(round(board_size - corner_size - (index - 1) * step))
            return pygame.Rect(x_start, board_size - corner_size, x_end - x_start, corner_size)
            
        elif 10 < index < 20:
            y_start = int(round(board_size - corner_size - (index - 10) * step))
            y_end = int(round(board_size - corner_size - (index - 11) * step))
            return pygame.Rect(0, y_start, corner_size, y_end - y_start)
            
        elif 20 < index < 30:
            x_start = int(round(corner_size + (index - 21) * step))
            x_end = int(round(corner_size + (index - 20) * step))
            return pygame.Rect(x_start, 0, x_end - x_start, corner_size)
            
        elif 30 < index < 40:
            y_start = int(round(corner_size + (index - 31) * step))
            y_end = int(round(corner_size + (index - 30) * step))
            return pygame.Rect(board_size - corner_size, y_start, corner_size, y_end - y_start)

        return pygame.Rect(0, 0, 0, 0)

    def draw_text_centered(self, surface, text, font, color, center_pos, rotation=0):
        """
        Pristine centered font printer supporting angular text rotation.
        """
        text_surf = font.render(text, True, color)
        if rotation:
            text_surf = pygame.transform.rotate(text_surf, rotation)
        rect = text_surf.get_rect(center=center_pos)
        surface.blit(text_surf, rect)

    def render_tile_details(self, index: int, rect: pygame.Rect):
        """
        Draws tiles groups, taxes, railroads, prices, and owner badge overlays.
        """
        tile = constants.TILES[index]
        bg_col = (250, 252, 250) if tile["group"] != "CORNER" else (235, 238, 235)
        
        # 1. Base rectangle
        pygame.draw.rect(self.screen, bg_col, rect)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, rect, 1)
        
        # 2. Rotation parameters for labels
        rotation = 0
        if 10 < index < 20:
            rotation = 270
        elif 30 < index < 40:
            rotation = 90
        elif 20 < index < 30:
            rotation = 180
            
        # 3. Draw color band for properties
        if tile["color"] is not None:
            band_size = 18
            if index < 10:
                band_rect = pygame.Rect(rect.x, rect.y, rect.width, band_size)
            elif index < 20:
                band_rect = pygame.Rect(rect.x + rect.width - band_size, rect.y, band_size, rect.height)
            elif index < 30:
                band_rect = pygame.Rect(rect.x, rect.y + rect.height - band_size, rect.width, band_size)
            else:
                band_rect = pygame.Rect(rect.x, rect.y, band_size, rect.height)
                
            pygame.draw.rect(self.screen, tile["color"], band_rect)
            pygame.draw.rect(self.screen, constants.COLOR_BORDER, band_rect, 1)

        # 4. Render labels
        name = tile["name"]
        group = tile["group"]
        
        if group == "CORNER":
            sub_text = tile.get("subtext", "")
            self.draw_text_centered(self.screen, name, self.tile_bold_font, (12, 12, 12), (rect.centerx, rect.centery - 10), 0)
            if sub_text:
                self.draw_text_centered(self.screen, sub_text, self.tile_small_font, (200, 30, 30), (rect.centerx, rect.centery + 12), 0)
        else:
            parts = name.split(" ")
            if len(parts) > 1 and len(name) > 8:
                self.draw_text_centered(self.screen, parts[0], self.tile_font, constants.COLOR_TEXT, (rect.centerx, rect.centery - 5), rotation)
                self.draw_text_centered(self.screen, " ".join(parts[1:]), self.tile_font, constants.COLOR_TEXT, (rect.centerx, rect.centery + 5), rotation)
            else:
                self.draw_text_centered(self.screen, name, self.tile_bold_font, constants.COLOR_TEXT, rect.center, rotation)
                
            # Prices or subgroups markings
            if "price" in tile:
                price_text = f"${tile['price']}"
                if index < 10:
                    pos = (rect.centerx, rect.y + rect.height - 10)
                elif index < 20:
                    pos = (rect.x + 10, rect.centery)
                elif index < 30:
                    pos = (rect.centerx, rect.y + 10)
                else:
                    pos = (rect.x + rect.width - 10, rect.centery)
                self.draw_text_centered(self.screen, price_text, self.tile_small_font, (20, 110, 20), pos, rotation)
            elif "subtext" in tile:
                sub = tile["subtext"]
                if index < 10:
                    pos = (rect.centerx, rect.y + rect.height - 10)
                elif index < 20:
                    pos = (rect.x + 10, rect.centery)
                elif index < 30:
                    pos = (rect.centerx, rect.y + 10)
                else:
                    pos = (rect.x + rect.width - 10, rect.centery)
                self.draw_text_centered(self.screen, sub, self.tile_small_font, (120, 10, 10), pos, rotation)

        # 5. Render Owner badge indicator (Success Criteria 5)
        prop = self.properties.get(index)
        if prop and prop.owner:
            # Layout neat circular badges in opposite corners of properties
            # This handles up to 8 owners clearly without blocking content
            if index < 10:
                pos = (rect.x + 12, rect.y + 12)
            elif index < 20:
                pos = (rect.x + rect.width - 12, rect.y + 12)
            elif index < 30:
                pos = (rect.x + rect.width - 12, rect.y + rect.height - 12)
            else:
                pos = (rect.x + 12, rect.y + rect.height - 12)
                
            badge_rect = pygame.Rect(pos[0] - 8, pos[1] - 6, 17, 13)
            pygame.draw.rect(self.screen, prop.owner.color, badge_rect, border_radius=2)
            pygame.draw.rect(self.screen, (10, 10, 10), badge_rect, 1, border_radius=2)
            
            owner_text = f"P{prop.owner.player_id + 1}"
            self.draw_text_centered(self.screen, owner_text, self.tile_small_font, constants.COLOR_WHITE, badge_rect.center, 0)

    def draw_dice_visuals(self, x_center, y_pos):
        """
        Renders two white dice with actual calculated dots nicely.
        """
        self.draw_single_die(x_center - 55, y_pos, self.dice1)
        self.draw_single_die(x_center + 5, y_pos, self.dice2)
        
        self.draw_text_centered(
            self.screen, 
            f"Roll Sum: {self.roll_sum}", 
            self.ui_font, 
            constants.COLOR_TEXT, 
            (x_center, y_pos + 60)
        )

    def draw_single_die(self, x, y, val):
        size = 48
        die_rect = pygame.Rect(x, y, size, size)
        
        pygame.draw.rect(self.screen, constants.COLOR_DICE_BG, die_rect, border_radius=6)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, die_rect, 2, border_radius=6)
        
        p1 = (12, 12)
        p2 = (36, 12)
        p3 = (12, 24)
        p4 = (24, 24)
        p5 = (36, 24)
        p6 = (12, 36)
        p7 = (36, 36)
        
        layout = {
            1: [p4],
            2: [p1, p7],
            3: [p1, p4, p7],
            4: [p1, p2, p6, p7],
            5: [p1, p2, p4, p6, p7],
            6: [p1, p2, p3, p5, p6, p7]
        }
        
        for p in layout.get(val, []):
            pygame.draw.circle(self.screen, (24, 24, 24), (x + p[0], y + p[1]), 4)

    def draw_buy_popup(self):
        """
        Draws a clean, gorgeous popup dialog over center of the screen when landing on unowned property.
        """
        if not self.active_popup:
            return
            
        prop = self.active_popup["property"]
        player = self.active_popup["player"]
        
        # 1. Dim board center (600x600 translucent mask)
        dialog_mask = pygame.Surface((constants.BOARD_SIZE - 200, constants.BOARD_SIZE - 200), pygame.SRCALPHA)
        dialog_mask.fill((15, 23, 42, 185))
        self.screen.blit(dialog_mask, (constants.CORNER_SIZE, constants.CORNER_SIZE))
        
        # 2. Main cardboard base rect
        card_rect = pygame.Rect(230, 260, 340, 220)
        pygame.draw.rect(self.screen, (253, 255, 253), card_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, card_rect, 2, border_radius=8)
        
        # Group stripe rendering colors mapping
        group_colors = {
            "BROWN": (140, 81, 10),
            "LIGHTBLUE": (170, 218, 233),
            "PINK": (197, 17, 98),
            "ORANGE": (245, 124, 0),
            "RED": (229, 57, 53),
            "YELLOW": (251, 192, 45),
            "GREEN": (46, 125, 50),
            "BLUE": (21, 101, 192),
            "RAILROAD": (60, 60, 60),
            "UTILITY": (212, 175, 55)
        }
        stripe_color = group_colors.get(prop.group, (33, 33, 33))
        
        # Drawer color stripe
        stripe_rect = pygame.Rect(232, 262, 336, 32)
        pygame.draw.rect(self.screen, stripe_color, stripe_rect, border_radius=6)
        
        # Stripe title
        self.draw_text_centered(
            self.screen, 
            f"{prop.group} PROPERTY CARD", 
            self.tile_bold_font, 
            constants.COLOR_WHITE if prop.group != "LIGHTBLUE" else (33, 33, 33), 
            stripe_rect.center
        )
        
        # Information details
        self.draw_text_centered(self.screen, f"{prop.name}", self.title_font, constants.COLOR_TEXT, (400, 315))
        self.draw_text_centered(self.screen, f"PRICE: ${prop.price}  |  BASE RENT: ${prop.base_rent}", self.ui_font, (20, 110, 20), (400, 350))
        self.draw_text_centered(self.screen, f"Active Buyer: {player.name} (${player.cash})", self.sub_font, constants.COLOR_TEXT, (400, 385))
        
        # Buttons hover check and rendering
        mouse_pos = pygame.mouse.get_pos()
        
        # Yes button
        yes_hover = self.popup_yes_rect.collidepoint(mouse_pos)
        yes_color = (195, 255, 195) if yes_hover else (220, 245, 220)
        pygame.draw.rect(self.screen, yes_color, self.popup_yes_rect, border_radius=6)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.popup_yes_rect, 2, border_radius=6)
        self.draw_text_centered(self.screen, "YES (Buy Property)", self.sub_font, constants.COLOR_TEXT, self.popup_yes_rect.center)
        
        # No button
        no_hover = self.popup_no_rect.collidepoint(mouse_pos)
        no_color = (255, 195, 195) if no_hover else (245, 220, 220)
        pygame.draw.rect(self.screen, no_color, self.popup_no_rect, border_radius=6)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.popup_no_rect, 2, border_radius=6)
        self.draw_text_centered(self.screen, "NO (Decline)", self.sub_font, constants.COLOR_TEXT, self.popup_no_rect.center)

    def draw_jail_popup(self):
        """
        Draws an interactive jail visual popup showing Option A/B paths.
        """
        active_p = self.get_current_player()
        if not active_p.is_in_jail or self.has_rolled_this_turn:
            return

        # 1. Dim board center
        dialog_mask = pygame.Surface((constants.BOARD_SIZE - 200, constants.BOARD_SIZE - 200), pygame.SRCALPHA)
        dialog_mask.fill((15, 23, 42, 195))
        self.screen.blit(dialog_mask, (constants.CORNER_SIZE, constants.CORNER_SIZE))

        # 2. Base panel
        card_rect = pygame.Rect(230, 260, 340, 220)
        pygame.draw.rect(self.screen, (253, 255, 253), card_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, card_rect, 2, border_radius=8)

        # Draw red colored prison badge stripe
        stripe_rect = pygame.Rect(232, 262, 336, 32)
        pygame.draw.rect(self.screen, (180, 20, 20), stripe_rect, border_radius=6)

        self.draw_text_centered(
            self.screen,
            "IN JAIL CONFINEMENT",
            self.tile_bold_font,
            constants.COLOR_WHITE,
            stripe_rect.center
        )

        self.draw_text_centered(self.screen, f"{active_p.name}", self.title_font, active_p.color, (400, 315))

        # Forced payment trigger check
        if active_p.jail_turns_count >= 3:
            self.draw_text_centered(self.screen, "Max Turns Over! 3 tries failed.", self.ui_font, (180, 20, 20), (400, 350))
            self.draw_text_centered(self.screen, f"Must pay $50 Escape Fine.", self.sub_font, constants.COLOR_TEXT, (400, 380))
            
            mouse_pos = pygame.mouse.get_pos()
            btn_hover = self.jail_ok_rect.collidepoint(mouse_pos)
            btn_color = (255, 195, 195) if btn_hover else (245, 220, 220)
            pygame.draw.rect(self.screen, btn_color, self.jail_ok_rect, border_radius=6)
            pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.jail_ok_rect, 2, border_radius=6)
            self.draw_text_centered(self.screen, "Pay $50 & Release", self.sub_font, constants.COLOR_TEXT, self.jail_ok_rect.center)
        else:
            self.draw_text_centered(self.screen, f"Remaining Attempts: {3 - active_p.jail_turns_count}/3", self.ui_font, constants.COLOR_TEXT, (400, 345))
            self.draw_text_centered(self.screen, "Select escape route:", self.sub_font, (120, 120, 120), (400, 362))

            mouse_pos = pygame.mouse.get_pos()

            # Option A payment button
            pay_hover = self.jail_pay_rect.collidepoint(mouse_pos)
            pay_color = (195, 255, 195) if pay_hover else (220, 245, 220)
            pygame.draw.rect(self.screen, pay_color, self.jail_pay_rect, border_radius=6)
            pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.jail_pay_rect, 2, border_radius=6)
            self.draw_text_centered(self.screen, "Pay $50 [P]", self.sub_font, constants.COLOR_TEXT, self.jail_pay_rect.center)

            # Option B rolling doubles button
            roll_hover = self.jail_roll_rect.collidepoint(mouse_pos)
            roll_color = (195, 220, 255) if roll_hover else (220, 235, 255)
            pygame.draw.rect(self.screen, roll_color, self.jail_roll_rect, border_radius=4)
            pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.jail_roll_rect, 2, border_radius=4)
            self.draw_text_centered(self.screen, "Roll Doubles [R]", self.sub_font, constants.COLOR_TEXT, self.jail_roll_rect.center)

    def draw_card_popup(self):
        """
        Draws action cards visual layouts for Chance & Community Chest.
        """
        if not self.active_card_popup:
            return

        card = self.active_card_popup["card"]
        deck_name = self.active_card_popup["deck_name"]
        player = self.active_card_popup["player"]

        # 1. Dim board center
        dialog_mask = pygame.Surface((constants.BOARD_SIZE - 200, constants.BOARD_SIZE - 200), pygame.SRCALPHA)
        dialog_mask.fill((15, 23, 42, 195))
        self.screen.blit(dialog_mask, (constants.CORNER_SIZE, constants.CORNER_SIZE))

        # 2. Card base rect
        card_rect = pygame.Rect(230, 260, 340, 220)
        pygame.draw.rect(self.screen, (253, 255, 253), card_rect, border_radius=8)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, card_rect, 2, border_radius=8)

        # Header band color
        stripe_color = (197, 17, 98) if deck_name == "Chance" else (32, 201, 151)
        stripe_rect = pygame.Rect(232, 262, 336, 32)
        pygame.draw.rect(self.screen, stripe_color, stripe_rect, border_radius=6)

        self.draw_text_centered(
            self.screen,
            f"{deck_name.upper()} TELEGRAM",
            self.tile_bold_font,
            constants.COLOR_WHITE,
            stripe_rect.center
        )

        self.draw_text_centered(self.screen, f"Drawn by {player.name}", self.sub_font, (100, 100, 100), (400, 312))

        # Split text logic
        words = card["text"].split(" ")
        lines = []
        curr = ""
        for w in words:
            if len(curr + " " + w) < 28:
                curr += " " + w if curr else w
            else:
                lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)

        for i, line_str in enumerate(lines[:2]):
            self.draw_text_centered(self.screen, line_str, self.tile_bold_font, constants.COLOR_TEXT, (400, 344 + i * 20))

        # OK button
        mouse_pos = pygame.mouse.get_pos()
        btn_hover = self.card_ok_rect.collidepoint(mouse_pos)
        btn_color = (220, 245, 220) if btn_hover else (240, 240, 240)
        pygame.draw.rect(self.screen, btn_color, self.card_ok_rect, border_radius=6)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.card_ok_rect, 2, border_radius=6)
        self.draw_text_centered(self.screen, "REVEAL EFFECT / OK", self.sub_font, constants.COLOR_TEXT, self.card_ok_rect.center)

    def draw_save_popup(self):
        """
        Draws a clean, gorgeous save game popup modal in the center of the board.
        """
        if not getattr(self, "active_save_overlay", False):
            return
            
        # 1. Dim board center
        dialog_mask = pygame.Surface((constants.BOARD_SIZE - 200, constants.BOARD_SIZE - 200), pygame.SRCALPHA)
        dialog_mask.fill((15, 23, 42, 210))
        self.screen.blit(dialog_mask, (constants.CORNER_SIZE, constants.CORNER_SIZE))
        
        # 2. Card base rect
        card_rect = pygame.Rect(230, 220, 340, 310)
        pygame.draw.rect(self.screen, (30, 41, 59), card_rect, border_radius=12)
        pygame.draw.rect(self.screen, (99, 102, 241), card_rect, 2, border_radius=12)
        
        # Header banner stripe
        stripe_rect = pygame.Rect(232, 222, 336, 36)
        pygame.draw.rect(self.screen, (99, 102, 241), stripe_rect, border_radius=10)
        
        self.draw_text_centered(
            self.screen, 
            "SAVE CURRENT GAME", 
            self.tile_bold_font, 
            constants.COLOR_WHITE, 
            stripe_rect.center
        )
        
        mouse_pos = pygame.mouse.get_pos()
        
        # Display each slot choice
        for idx, rect in enumerate(self.save_slot_rects):
            slot_num = idx + 1
            filename = f"save_slot_{slot_num}.json"
            is_hover = rect.collidepoint(mouse_pos)
            
            slot_exists = os.path.exists(filename)
            slot_label = f"Slot {slot_num}: (Empty Slot)"
            if slot_exists:
                try:
                    with open(filename, "r") as f:
                        data = json.load(f)
                    timestamp = data.get("timestamp", "Unknown Date")
                    players = data.get("players", [])
                    slot_label = f"Slot {slot_num}: {len(players)}P ({timestamp[2:10]} {timestamp[11:16]})"
                except:
                    slot_label = f"Slot {slot_num}: (Corrupted Format)"
                    
            if is_hover:
                bg_color = (16, 185, 129) if slot_exists else (79, 70, 229)
                border_color = constants.COLOR_WHITE
                text_color = constants.COLOR_WHITE
            else:
                bg_color = (16, 124, 76) if slot_exists else (47, 55, 71)
                border_color = (74, 85, 104)
                text_color = (250, 250, 250)
                
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
            pygame.draw.rect(self.screen, border_color, rect, 2, border_radius=6)
            self.draw_text_centered(self.screen, slot_label, self.ui_font, text_color, rect.center)
            
        # Cancel Button
        is_cancel_hover = self.save_cancel_rect.collidepoint(mouse_pos)
        cancel_bg = (239, 68, 68) if is_cancel_hover else (185, 28, 28)
        pygame.draw.rect(self.screen, cancel_bg, self.save_cancel_rect, border_radius=6)
        pygame.draw.rect(self.screen, constants.COLOR_WHITE, self.save_cancel_rect, 2, border_radius=6)
        self.draw_text_centered(self.screen, "CANCEL", self.ui_font, constants.COLOR_WHITE, self.save_cancel_rect.center)

    def render_board_layout(self):
        """
        Draws the Monopoly board, edge spaces, player info, and button layers.
        """
        self.screen.fill(constants.COLOR_BACKGROUND)
        
        # 1. Soft green Monopoly Board inner rectangular space
        center_size = constants.BOARD_SIZE - 2 * constants.CORNER_SIZE
        board_rect = pygame.Rect(constants.CORNER_SIZE, constants.CORNER_SIZE, center_size, center_size)
        pygame.draw.rect(self.screen, constants.COLOR_BOARD_BG, board_rect)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, board_rect, 2)
        
        # 2. Render all 40 bounding tiles
        for idx in range(40):
            tile_rect = self.get_tile_rect(idx)
            self.render_tile_details(idx, tile_rect)
            
        # 3. Draw middle "MONOPOLY" banner text
        self.draw_text_centered(
            self.screen, 
            "MONOPOLY", 
            pygame.font.SysFont(constants.FONT_FAMILY, 38, bold=True), 
            (180, 20, 20), 
            (400, 155)
        )
        self.draw_text_centered(
            self.screen, 
            "Local Multiplayer Edition", 
            self.sub_font, 
            constants.COLOR_TEXT, 
            (400, 200)
        )

        # 4. Draw active player information in board core
        act_p = self.get_current_player()
        self.draw_text_centered(
            self.screen,
            f"Current Turn: {act_p.name}" + (" [JAIL]" if act_p.is_in_jail else ""),
            self.title_font,
            act_p.color,
            (400, 235)
        )
        
        # 5. Draw the dice blocks
        self.draw_dice_visuals(400, 265)
        
        # 6. Button states drawing: disable controls when buying popups or jail choices block progress
        mouse_pos = pygame.mouse.get_pos()
        
        # Block ROLL button under lock states
        is_roll_blocked = (
            self.has_rolled_this_turn or 
            self.active_popup is not None or 
            self.active_card_popup is not None or 
            (act_p.is_in_jail and not self.has_rolled_this_turn)
        )
        
        # Block PASS button under lock states
        is_pass_blocked = (
            not self.has_rolled_this_turn or # Block pass before rolling (Success Criteria 2)
            self.active_popup is not None or 
            self.active_card_popup is not None or 
            (act_p.is_in_jail and not self.has_rolled_this_turn)
        )

        if is_roll_blocked: 
            roll_color = (220, 220, 220)
        else:
            roll_color = (190, 255, 190) if self.roll_btn_rect.collidepoint(mouse_pos) else (210, 245, 210)
        pygame.draw.rect(self.screen, roll_color, self.roll_btn_rect, border_radius=5)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.roll_btn_rect, 2, border_radius=5)
        self.draw_text_centered(self.screen, "ROLL DICE", self.ui_font, (120, 120, 120) if is_roll_blocked else constants.COLOR_TEXT, self.roll_btn_rect.center)
        
        if is_pass_blocked:
            pass_color = (220, 220, 220)
        else:
            pass_color = (245, 200, 200) if self.pass_btn_rect.collidepoint(mouse_pos) else (235, 220, 220)
        pygame.draw.rect(self.screen, pass_color, self.pass_btn_rect, border_radius=5)
        pygame.draw.rect(self.screen, constants.COLOR_BORDER, self.pass_btn_rect, 2, border_radius=5)
        self.draw_text_centered(self.screen, "PASS TURN", self.ui_font, (120, 120, 120) if is_pass_blocked else constants.COLOR_TEXT, self.pass_btn_rect.center)
        
        # 6.5 Draw manual END GAME button
        end_color = (254, 226, 226) if self.end_btn_rect.collidepoint(mouse_pos) else (254, 242, 242)
        pygame.draw.rect(self.screen, end_color, self.end_btn_rect, border_radius=5)
        pygame.draw.rect(self.screen, (220, 38, 38), self.end_btn_rect, 2, border_radius=5)
        self.draw_text_centered(self.screen, "END GAME", self.ui_font, (185, 28, 28), self.end_btn_rect.center)
        
        # 6.6 Draw manual SAVE GAME button
        save_color = (224, 242, 254) if self.save_btn_rect.collidepoint(mouse_pos) else (240, 253, 250)
        pygame.draw.rect(self.screen, save_color, self.save_btn_rect, border_radius=5)
        pygame.draw.rect(self.screen, (3, 105, 161), self.save_btn_rect, 2, border_radius=5)
        self.draw_text_centered(self.screen, "SAVE GAME", self.ui_font, (3, 105, 161), self.save_btn_rect.center)
        
        # 7. Last Event Logger display line
        self.draw_text_centered(self.screen, self.last_event_msg, self.ui_font, self.last_event_color, (400, 480))
        
        # 7.5 Draw POPUP overlays
        self.draw_buy_popup()
        self.draw_jail_popup()
        self.draw_card_popup()
        self.draw_save_popup()
        
        # 8. Rendering token circles on matching coordinates
        self.draw_player_tokens()

    def draw_player_tokens(self):
        """
        Distributes visual coordinate offsets so up to 8 tokens overlap neatly inside a tile index.
        """
        for i, player in enumerate(self.players):
            rect = self.get_tile_rect(player.position)
            
            offsets = [
                (-18, -18), (18, -18), 
                (-18, 18), (18, 18),
                (-30, 0), (30, 0), 
                (0, -30), (0, 30)
            ]
            dx, dy = offsets[i % len(offsets)]
            tok_x = rect.centerx + dx
            tok_y = rect.centery + dy
            
            is_active = (i == self.current_turn_index)
            radius = 11 if is_active else 8
            border_w = 3 if is_active else 1
            
            pygame.draw.circle(self.screen, player.color, (tok_x, tok_y), radius)
            pygame.draw.circle(self.screen, (10, 10, 10), (tok_x, tok_y), radius, border_w)
            
            num_surf = self.tile_small_font.render(str(i + 1), True, constants.COLOR_WHITE)
            num_rect = num_surf.get_rect(center=(tok_x, tok_y))
            self.screen.blit(num_surf, num_rect)

    def render_hud(self):
        """
        Renders a gorgeous right-side dedicated panel holding player ledgers, 
        outstanding portfolio statuses and real-time game logs.
        """
        sidebar_x = 800
        sidebar_width = 350
        
        # 1. Clean background fill & divider line
        pygame.draw.rect(self.screen, (15, 23, 42), (sidebar_x + 3, 0, sidebar_width - 3, 800))
        pygame.draw.line(self.screen, (47, 55, 71), (sidebar_x, 0), (sidebar_x, 800), 3)
        
        # --- PLAYER STATUS PANEL --- (Success Criteria 15/Move display)
        # Panel Title
        self.draw_text_centered(
            self.screen, 
            "★ PLAYER STATUS PANEL ★", 
            self.ui_font, 
            (129, 140, 248), # Neon Indigo/blue
            (sidebar_x + sidebar_width // 2, 25)
        )
        pygame.draw.line(self.screen, (47, 55, 71), (sidebar_x + 15, 45), (sidebar_x + sidebar_width - 15, 45), 1)
        
        # Combine active and eliminated players for visual tracking
        active_players = self.players
        eliminated_p = getattr(self, 'eliminated_players', [])
        
        # List all players
        y_offset = 60
        for idx, player in enumerate(active_players):
            is_active = (idx == self.current_turn_index)
            
            # Active Player Highlight Container Box
            if is_active:
                hl_rect = pygame.Rect(sidebar_x + 15, y_offset - 4, sidebar_width - 30, 42)
                pygame.draw.rect(self.screen, (30, 41, 59), hl_rect, border_radius=6)
                pygame.draw.rect(self.screen, (99, 102, 241), hl_rect, 2, border_radius=6)
                
            # Render Color Swatch circle
            pygame.draw.circle(self.screen, player.color, (sidebar_x + 30, y_offset + 16), 8)
            pygame.draw.circle(self.screen, constants.COLOR_WHITE, (sidebar_x + 30, y_offset + 16), 8, 1)
            
            prefix = "★ " if is_active else "  "
            owned_props = [p.name.replace(" Ave", "").replace(" Pl", "") for p in self.properties.values() if p.owner == player]
            props_str = f" | Props: {len(owned_props)}"
            jail_str = " [IN JAIL]" if player.is_in_jail else ""
            
            # Player line 1: Name and Cash Wallet
            p_text = f"{prefix}{player.name}: ${player.cash:,}{jail_str}"
            self.draw_text_left(
                self.screen,
                p_text,
                self.ui_font if is_active else self.sub_font,
                player.color if is_active else (226, 232, 240),
                (sidebar_x + 48, y_offset + 2)
            )
            
            # Player line 2: Position and properties summary
            p_desc = f"Space {player.position} ({constants.TILES[player.position]['name']}){props_str}"
            self.draw_text_left(
                self.screen,
                p_desc,
                self.tile_font if not is_active else self.sub_font,
                (148, 163, 184),
                (sidebar_x + 48, y_offset + 18)
            )
            
            y_offset += 48
            
        # List eliminated players
        for player in eliminated_p:
            pygame.draw.circle(self.screen, (71, 85, 105), (sidebar_x + 30, y_offset + 12), 6)
            p_text = f"❌ {player.name} (BANKRUPT)"
            self.draw_text_left(
                self.screen,
                p_text,
                self.sub_font,
                (100, 116, 139),
                (sidebar_x + 48, y_offset + 2)
            )
            y_offset += 26
            
        # --- DEDICATED ACTIVITY LOG WINDOW --- (Success Criteria 15)
        log_y = 420
        
        # Display Box Frame
        box_rect = pygame.Rect(sidebar_x + 15, log_y + 30, sidebar_width - 30, 310)
        pygame.draw.rect(self.screen, (10, 15, 30), box_rect, border_radius=8)
        pygame.draw.rect(self.screen, (47, 55, 71), box_rect, 2, border_radius=8)
        
        # Upper header styling block inside the box itself so it does not interfere above
        header_bar_rect = pygame.Rect(sidebar_x + 16, log_y + 31, sidebar_width - 32, 34)
        pygame.draw.rect(self.screen, (30, 41, 59), header_bar_rect, border_radius=6)
        pygame.draw.line(self.screen, (47, 55, 71), (sidebar_x + 15, log_y + 65), (sidebar_x + sidebar_width - 15, log_y + 65), 1)
        
        # Event log header text inside the box top
        self.draw_text_centered(
            self.screen, 
            "▶ REAL-TIME EVENT LOG ◀", 
            self.ui_font, 
            (244, 63, 94), # Rose 500
            (sidebar_x + sidebar_width // 2, log_y + 48)
        )
        
        # Render the last 8 items, starting below the inside header separator line
        log_items = getattr(self, 'activity_log_history', [])
        disp_y = log_y + 75
        for text, col in log_items:
            # Render list item indicators
            pygame.draw.polygon(self.screen, col, [
                (sidebar_x + 24, disp_y + 7),
                (sidebar_x + 29, disp_y + 10),
                (sidebar_x + 24, disp_y + 13)
            ])
            
            wrapped_lines = self.wrap_text_line(text, 280)
            for file_line in wrapped_lines:
                self.draw_text_left(
                    self.screen,
                    file_line,
                    self.tile_bold_font,
                    col,
                    (sidebar_x + 35, disp_y)
                )
                disp_y += 15
            disp_y += 7

    def run(self):
        """
        Main runner executing loop checks and visual ticks.
        """
        print("[GAME ENGINE] Initializing game loop...")
        
        while self.running:
            self.handle_events()
            if not self.game_started:
                self.draw_start_screen()
            elif self.game_over:
                self.draw_game_over_screen()
            else:
                self.render_board_layout()
                self.render_hud()
                
            pygame.display.flip()
            self.clock.tick(constants.FPS)
            
        pygame.quit()
        print("[GAME ENGINE] Shutdown complete. Project files closed successfully.")
        sys.exit()

if __name__ == "__main__":
    game = MonopolyGame()
    game.run()
