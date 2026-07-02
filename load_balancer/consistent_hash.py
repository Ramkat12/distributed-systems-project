class ConsistentHashMap:
    def __init__(self, num_slots=512, num_virtual=9):
        self.num_slots = num_slots        # M = 512
        self.num_virtual = num_virtual    # K = 9
        self.hash_map = [None] * num_slots  # the ring

    # H(i) = i^2 + 2i + 17
    def request_hash(self, req_id):
        return (req_id**2 + 2*req_id + 17) % self.num_slots

    # Φ(i, j) = i^2 + j^2 + 2j + 25
    def server_hash(self, server_id, virtual_id):
        i, j = server_id, virtual_id
        return (i**2 + j**2 + 2*j + 25) % self.num_slots

    def add_server(self, server_id):
        for j in range(self.num_virtual):
            slot = self.server_hash(server_id, j)
            # Linear probing if slot is taken
            while self.hash_map[slot] is not None:
                slot = (slot + 1) % self.num_slots
            self.hash_map[slot] = server_id

    def remove_server(self, server_id):
        for slot in range(self.num_slots):
            if self.hash_map[slot] == server_id:
                self.hash_map[slot] = None

    def get_server(self, req_id):
        slot = self.request_hash(req_id)
        # Walk clockwise to find nearest server
        for i in range(self.num_slots):
            candidate = self.hash_map[(slot + i) % self.num_slots]
            if candidate is not None:
                return candidate
        return None  # no servers at all