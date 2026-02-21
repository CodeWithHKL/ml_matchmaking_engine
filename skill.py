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
        # Total weight for balancing: MMR * Size
        self.total_mmr_weight = sum(p.mmr for p in players)
        self.entry_time = min(p.entry_time for p in players)

# --- 2. The Engine ---

class ClassicMatchmaker:
    def __init__(self):
        self.queue = []
        self.base_mmr_diff = 300  # Classic allows looser skill gaps
        self.expansion_rate = 20   # MMR gap expands by 20 every second

    def add_to_queue(self, party):
        self.queue.append(party)

    def find_match(self):
        if sum(p.size for p in self.queue) < 10:
            return None

        # Sort by wait time (FIFO)
        self.queue.sort(key=lambda x: x.entry_time)

        for i, lead_party in enumerate(self.queue):
            candidate_pool = [lead_party]
            current_slots = lead_party.size
            
            # Dynamic MMR threshold based on how long the lead party has waited
            wait_time = time.time() - lead_party.entry_time
            dynamic_bracket = self.base_mmr_diff + (wait_time * self.expansion_rate)

            # Gather 10 slots worth of parties
            for j, other_party in enumerate(self.queue):
                if i == j: continue
                
                # Check if this party fits in the 10-player pool
                if current_slots + other_party.size <= 10:
                    # Skill check against the lead party
                    if abs(other_party.avg_mmr - lead_party.avg_mmr) <= dynamic_bracket:
                        candidate_pool.append(other_party)
                        current_slots += other_party.size
            
            if current_slots == 10:
                return self.optimize_and_finalize(candidate_pool)
        
        return None

    def optimize_and_finalize(self, parties):
        """
        Distributes parties into two teams (5v5) to minimize MMR difference.
        Uses a Greedy Balance algorithm: 
        Always add the next party to the team with the lower current total MMR.
        """
        # Sort parties by size (largest first) to handle the 'big blocks' like 4-mans first
        parties.sort(key=lambda x: x.size, reverse=True)
        
        team_a, team_b = [], []
        sum_a, sum_b = 0, 0
        slots_a, slots_b = 0, 0

        for p in parties:
            # Add to Team A if it has room AND (it's weaker OR Team B is full)
            if (slots_a + p.size <= 5) and (sum_a <= sum_b or slots_b + p.size > 5):
                team_a.append(p)
                sum_a += p.total_mmr_weight
                slots_a += p.size
            else:
                team_b.append(p)
                sum_b += p.total_mmr_weight
                slots_b += p.size

        # Remove matched parties from queue
        for p in parties:
            self.queue.remove(p)
            
        return team_a, team_b

# --- 3. Simulation Loop ---

def run_simulation():
    engine = ClassicMatchmaker()
    match_count = 0
    
    print("🚀 MLBB Classic Server Live...")

    while True:
        # Simulate incoming traffic
        # Classic allows 1, 2, 3, 4, 5 man parties
        p_size = random.choice([1, 1, 1, 2, 2, 3, 4, 5])
        new_players = [Player(f"User-{random.randint(100,999)}", random.randint(1000, 3500)) for _ in range(p_size)]
        engine.add_to_queue(Party(new_players))

        # Attempt Matchmaking
        match = engine.find_match()

        # UI Refresh
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"--- SERVER DASHBOARD ---")
        print(f"Queue: {sum(p.size for p in engine.queue)} players | Total Matches: {match_count}")
        print("-" * 30)

        if match:
            team_a, team_b = match
            match_count += 1
            
            # Calculate final stats
            m_a = sum(p.total_mmr_weight for p in team_a) / 5
            m_b = sum(p.total_mmr_weight for p in team_b) / 5
            
            print(f"✨ MATCH #{match_count} FOUND! ✨")
            print(f"Team A: {' + '.join([str(p.size) for p in team_a])} stack (Avg MMR: {m_a:.0f})")
            print(f"Team B: {' + '.join([str(p.size) for p in team_b])} stack (Avg MMR: {m_b:.0f})")
            print(f"MMR Delta: {abs(m_a - m_b):.1f}")
            time.sleep(4)
        else:
            if engine.queue:
                wait = time.time() - engine.queue[0].entry_time
                print(f"Status: Searching... (Oldest wait: {wait:.1f}s)")
        
        time.sleep(0.5)

if __name__ == "__main__":
    run_simulation()