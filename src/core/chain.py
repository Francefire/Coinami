from __future__ import annotations

import time

from src.core.block import Block, BlockHeader
from src.core.transaction import Transaction


class Chain:
    def __init__(self, difficulty: int = 3):
        self.difficulty = difficulty
        self.pending_transactions: list[Transaction] = []
        self.blocks: list[Block] = [self._create_genesis_block()]

    def _create_genesis_block(self) -> Block:
        header = BlockHeader(
            prev_hash="0" * 64,
            merkle_root="0" * 64,
            timestamp=0.0,
            nonce=0,
        )
        return Block(header, [])

    @property
    def last_block(self) -> Block:
        return self.blocks[-1]

    def _proof_of_work(self, block: Block) -> Block:
        """Incrémente le nonce jusqu'à ce que le hash commence par `difficulty` zéros."""
        target = "0" * self.difficulty
        block.b_header.nonce = 0
        while not block.calculate_hash().startswith(target):
            block.b_header.nonce += 1
        return block

    def mine_block(self) -> Block:
        """Mine un nouveau bloc avec les transactions en attente et vide le mempool."""
        block = Block.create(
            prev_hash=self.last_block.calculate_hash(),
            transactions=list(self.pending_transactions),
        )
        block = self._proof_of_work(block)
        self.blocks.append(block)
        self.pending_transactions = []
        return block

    def add_block(self, block: Block) -> bool:
        """Ajoute un bloc reçu depuis le réseau après vérification.

        Vérifie :
        - Le prev_hash pointe bien vers le dernier bloc de la chaîne.
        - Le hash du bloc satisfait la difficulté (PoW valide).
        """
        expected_prev = self.last_block.calculate_hash()
        if block.b_header.prev_hash != expected_prev:
            return False

        if not block.calculate_hash().startswith("0" * self.difficulty):
            return False

        self.blocks.append(block)
        return True

    def is_chain_valid(self) -> bool:
        """Parcourt tous les blocs et vérifie le chaînage et les hashs PoW."""
        for i in range(1, len(self.blocks)):
            current = self.blocks[i]
            previous = self.blocks[i - 1]

            # Le hash du bloc courant doit respecter la difficulté
            if not current.calculate_hash().startswith("0" * self.difficulty):
                return False

            # Le prev_hash du bloc courant doit pointer sur le hash du bloc précédent
            if current.b_header.prev_hash != previous.calculate_hash():
                return False

            # La merkle_root doit correspondre aux transactions
            if current.b_header.merkle_root != current.simplified_merkle_root():
                return False

        return True
