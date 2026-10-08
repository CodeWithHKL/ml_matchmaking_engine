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
        self.total_mmr_weight = sum(p.mmr for p in players)
        self.entry_time = min(p.entry_time for p in players)

# --- 2. The Engine ---

class ClassicMatchmaker:
    def __init__(self):
        self.queue = []
        self.base_mmr_diff = 300
        self.expansion_rate = 20

    def add_to_queue(self, party):
        self.queue.append(party)

    def find_match(self):
        if not self.queue: return None
        
        # Sort by wait time
        self.queue.sort(key=lambda x: x.entry_time)

        for i, lead_party in enumerate(self.queue):
            # --- CASE 1: 5-MAN PREMADE ---
            if lead_party.size == 5:
                # Strictly search for another 5-man party
                opponent = self.find_five_stack_opponent(lead_party, i)
                if opponent:
                    return self.finalize_five_vs_five(lead_party, opponent)
                continue # Skip to next party in queue

            # --- CASE 2: STANDARD COMBINATIONS (1, 2, 3, 4) ---
            candidate_pool = [lead_party]
            current_slots = lead_party.size
            
            wait_time = time.time() - lead_party.entry_time
            dynamic_bracket = self.base_mmr_diff + (wait_time * self.expansion_rate)

            for j, other_party in enumerate(self.queue):
                if i == j or other_party.size == 5: continue # EXCLUDE 5-mans
                
                if current_slots + other_party.size <= 10:
                    if abs(other_party.avg_mmr - lead_party.avg_mmr) <= dynamic_bracket:
                        candidate_pool.append(other_party)
                        current_slots += other_party.size
            
            if current_slots == 10:
                return self.optimize_and_finalize_standard(candidate_pool)
        
        return None

    def find_five_stack_opponent(self, party_a, idx):
        """Looks specifically for another 5-man party."""
        for j, party_b in enumerate(self.queue):
            if idx == j or party_b.size != 5: continue
            
            # Simple MMR check for 5v5
            wait_time = time.time() - party_a.entry_time
            if abs(party_a.avg_mmr - party_b.avg_mmr) <= (self.base_mmr_diff + wait_time * 10):
                return party_b
        return None

    def optimize_and_finalize_standard(self, parties):
        """Greedy balance for mixed parties (1-4 players)."""
        parties.sort(key=lambda x: x.size, reverse=True)
        
        team_a, team_b = [], []
        sum_a, sum_b, slots_a, slots_b = 0, 0, 0, 0

        for p in parties:
            if (slots_a + p.size <= 5) and (sum_a <= sum_b or slots_b + p.size > 5):
                team_a.append(p)
                sum_a += p.total_mmr_weight
                slots_a += p.size
            else:
                team_b.append(p)
                sum_b += p.total_mmr_weight
                slots_b += p.size

        for p in parties: self.queue.remove(p)
        return team_a, team_b

    def finalize_five_vs_five(self, p1, p2):
        """Quickly removes two 5-man parties."""
        self.queue.remove(p1)
        self.queue.remove(p2)
        return [p1], [p2]

# --- 3. Simulation Loop ---

def run_simulation():
    engine = ClassicMatchmaker()
    match_count = 0
    
    while True:
        # Simulate traffic with 5-man parties being rare (15% chance)
        p_size = random.choices([1, 2, 3, 4, 5], weights=[40, 20, 15, 10, 15])[0]
        players = [Player(f"U-{random.randint(100,999)}", random.randint(1000, 3500)) for _ in range(p_size)]
        engine.add_to_queue(Party(players))

        match = engine.find_match()

        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"--- MLBB CLASSIC SERVER (5v5 ISOLATION) ---")
        print(f"Queue Size: {sum(p.size for p in engine.queue)} | Matches: {match_count}")
        
        if match:
            team_a, team_b = match
            match_count += 1
            avg_a = sum(p.total_mmr_weight for p in team_a) / 5
            avg_b = sum(p.total_mmr_weight for p in team_b) / 5
            
            print(f"\n✅ MATCH FOUND")
            print(f"Team A: {'+'.join([str(p.size) for p in team_a])} stack (Avg MMR: {avg_a:.0f})")
            print(f"Team B: {'+'.join([str(p.size) for p in team_b])} stack (Avg MMR: {avg_b:.0f})")
            
            if len(team_a) == 1 and team_a[0].size == 5:
                print(">>> Note: This was a Strict 5v5 Premade match.")
            
            time.sleep(3)
        
        time.sleep(0.4)

if __name__ == "__main__":
    run_simulation()