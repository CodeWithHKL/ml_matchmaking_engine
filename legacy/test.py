import time
import random
import uuid
import os

# --- 1. Data Models ---

class Player:
    def __init__(self, name, mmr):
        self.id = uuid.uuid4().hex[:6]
        self.name = name
        self.mmr = mmr
        self.entry_time = time.time()

class Party:
    def __init__(self, players):
        self.players = players
        self.size = len(players)
        self.avg_mmr = sum(p.mmr for p in players) / self.size
        self.entry_time = min(p.entry_time for p in players)

# --- 2. The Classic Engine ---

class ClassicMatchmaker:
    def __init__(self):
        self.queue = []
        self.base_mmr_diff = 250  # Looser than Ranked
        self.expansion_rate = 25   # Expands quickly for speed

    def add_to_queue(self, party):
        # In Classic, 4-mans ARE allowed!
        self.queue.append(party)

    def find_match(self):
        if sum(p.size for p in self.queue) < 10:
            return None

        self.queue.sort(key=lambda x: x.entry_time)

        for i, lead_party in enumerate(self.queue):
            # Attempt to form Team A
            team_a = self.fill_slots(lead_party, i, [])
            if team_a:
                # Attempt to form Team B (excluding Team A players)
                team_b = self.find_opponent(team_a)
                if team_b:
                    return (team_a, team_b)
        return None

    def fill_slots(self, lead_party, skip_idx, exclude_parties):
        """Standard 'Tetris' logic to reach exactly 5 slots."""
        team = [lead_party]
        current_slots = lead_party.size
        
        # Calculate dynamic skill range
        wait_time = time.time() - lead_party.entry_time
        allowed_diff = self.base_mmr_diff + (wait_time * self.expansion_rate)

        for j, party in enumerate(self.queue):
            if j == skip_idx or party in exclude_parties: continue
            
            # Party Integrity: Must fit in the 5-man boat
            if current_slots + party.size <= 5:
                # Skill Check
                if abs(party.avg_mmr - lead_party.avg_mmr) <= allowed_diff:
                    team.append(party)
                    current_slots += party.size
            
            if current_slots == 5:
                return team
        return None

    def find_opponent(self, team_a):
        # Look for another team starting from the first available party not in Team A
        for i, party in enumerate(self.queue):
            if party in team_a: continue
            
            team_b = self.fill_slots(party, i, team_a)
            if team_b:
                return team_b
        return None

    def finalize(self, team_parties):
        players = []
        for p in team_parties:
            players.extend(p.players)
            if p in self.queue: self.queue.remove(p)
        return players

# --- 3. Live Simulation ---

def run_classic_server():
    engine = ClassicMatchmaker()
    match_count = 0

    print("🕹️  MLBB Classic Matchmaker (4-Man Enabled) 🕹️")

    while True:
        # Generate varied party sizes [1, 2, 3, 4, 5]
        # In Classic, 4-man parties are common!
        p_size = random.choice([1, 1, 1, 2, 2, 3, 4, 5]) 
        players = [Player(f"User-{random.randint(10,99)}", random.randint(800, 3000)) for _ in range(p_size)]
        engine.add_to_queue(Party(players))

        result = engine.find_match()

        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"--- CLASSIC QUEUE STATUS ---")
        print(f"Waiting: {sum(p.size for p in engine.queue)} players | Matches Formed: {match_count}")
        
        if result:
            team_a_parties, team_b_parties = result
            pa = engine.finalize(team_a_parties)
            pb = engine.finalize(team_b_parties)
            match_count += 1
            
            print(f"\n🎉 CLASSIC MATCH FOUND! 🎉")
            print(f"Team A: {' + '.join([str(len(p.players)) for p in team_a_parties])} stack")
            print(f"Team B: {' + '.join([str(len(p.players)) for p in team_b_parties])} stack")
            print(f"Skill: {sum(p.mmr for p in pa)/5:.0f} vs {sum(p.mmr for p in pb)/5:.0f}")
            time.sleep(3)
        
        time.sleep(0.5)

if __name__ == "__main__":
    run_classic_server()