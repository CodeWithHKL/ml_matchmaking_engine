import time
import random
import uuid
import os

# --- 1. Data Models ---

class Player:
    def __init__(self, name, mmr, roles, region="SEA"):
        self.id = uuid.uuid4().hex[:6]
        self.name = name
        self.mmr = mmr
        self.roles = roles 
        self.region = region
        self.entry_time = time.time()

class Party:
    def __init__(self, players):
        self.players = players
        self.size = len(players)
        self.avg_mmr = sum(p.mmr for p in players) / self.size
        self.region = players[0].region
        self.entry_time = min(p.entry_time for p in players)

# --- 2. The Engine ---

class MLMatchmaker:
    def __init__(self):
        self.queue = []
        self.base_mmr_diff = 100  
        self.expansion_rate = 15  # MMR gap grows by 15 every second

    def add_to_queue(self, party):
        self.queue.append(party)

    def find_match(self):
        # We need at least 10 players total to form a 5v5
        if sum(p.size for p in self.queue) < 10:
            return None

        self.queue.sort(key=lambda x: x.entry_time)

        for i, lead_party in enumerate(self.queue):
            potential_group = [lead_party]
            current_count = lead_party.size
            
            # Logic: Higher wait time = wider MMR search
            wait_time = time.time() - lead_party.entry_time
            dynamic_bracket = self.base_mmr_diff + (wait_time * self.expansion_rate)

            for j, other_party in enumerate(self.queue):
                if i == j: continue
                
                mmr_fit = abs(other_party.avg_mmr - lead_party.avg_mmr) <= dynamic_bracket
                region_fit = other_party.region == lead_party.region
                
                if mmr_fit and region_fit:
                    if current_count + other_party.size <= 10:
                        potential_group.append(other_party)
                        current_count += other_party.size

            if current_count == 10:
                return self.form_teams(potential_group)
        return None

    def form_teams(self, parties):
        all_players = []
        for p in parties:
            all_players.extend(p.players)
            self.queue.remove(p)
        
        # Balance teams by MMR (Snake Draft)
        all_players.sort(key=lambda x: x.mmr, reverse=True)
        team_a = [all_players[0], all_players[3], all_players[4], all_players[7], all_players[8]]
        team_b = [all_players[1], all_players[2], all_players[5], all_players[6], all_players[9]]
        return team_a, team_b

# --- 3. Persistent Simulation Loop ---

def start_server():
    engine = MLMatchmaker()
    roles_list = ["Tank", "Mage", "MM", "Assn", "Supp", "Ftr"]
    match_count = 0

    print("🚀 ML Matchmaking Server Started...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            # 1. Randomly simulate new players joining (Simulates real-world traffic)
            if random.random() < 0.7:  # 70% chance a new party joins every 'tick'
                size = random.choice([1, 1, 1, 2, 3]) # Mostly solo, some duos/trios
                new_players = [
                    Player(f"User_{random.randint(100,999)}", random.randint(1000, 3000), random.sample(roles_list, 2))
                    for _ in range(size)
                ]
                engine.add_to_queue(Party(new_players))

            # 2. Try to find a match
            match = engine.find_match()

            # 3. Output Status
            os.system('cls' if os.name == 'nt' else 'clear') # Refresh console
            print(f"--- MLBB SERVER STATUS ---")
            print(f"Active Players in Queue: {sum(p.size for p in engine.queue)}")
            print(f"Total Matches Found Today: {match_count}")
            print("-" * 30)

            if match:
                team_a, team_b = match
                match_count += 1
                avg_a = sum(p.mmr for p in team_a) / 5
                avg_b = sum(p.mmr for p in team_b) / 5
                
                print(f"✨ MATCH #{match_count} CREATED! ✨")
                print(f"Team A (Avg MMR: {avg_a:.0f}): {[p.name for p in team_a]}")
                print(f"Team B (Avg MMR: {avg_b:.0f}): {[p.name for p in team_b]}")
                print(f"Skill Gap: {abs(avg_a - avg_b):.1f} MMR")
                time.sleep(3) # Pause so you can read the match result
            else:
                print("Searching for balanced players...")
                # Show the oldest player's wait time
                if engine.queue:
                    wait = time.time() - engine.queue[0].entry_time
                    print(f"Oldest party waiting: {wait:.1f}s")

            time.sleep(1) # Server "tick" rate

    except KeyboardInterrupt:
        print("\nServer shutting down. GG!")

if __name__ == "__main__":
    start_server()