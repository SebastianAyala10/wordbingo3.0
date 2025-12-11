from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random


class Room(models.Model):
    name = models.CharField(max_length=50)
    host = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosted_rooms",
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("waiting", "Waiting"),
            ("running", "Running"),
            ("finished", "Finished"),
        ],
        default="waiting",
    )
    wait_end_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    players = models.ManyToManyField(User, related_name="rooms", blank=True)

    def __str__(self):
        return f"{self.name} (id={self.id})"

    def remaining_seconds(self):
        now = timezone.now()
        diff = (self.wait_end_time - now).total_seconds()
        return max(0, int(diff))


# ---------------- PALABRAS ----------------

WORDS = [
    "SOL", "LUNA", "ESTRELLA", "CIELO", "NUBE", "AIRE", "VIENTO", "AGUA", "RIO",
    "LAGO", "MAR", "OCEANO", "PLAYA", "ARENA", "MONTAÑA", "BOSQUE", "ARBOL",
    "FLOR", "HOJA", "HIERBA", "FUEGO", "ROCA", "TIERRA", "NIEVE", "HIELO",
    "TRUENO", "RAYO", "LLUVIA", "TORMENTA", "BRUMA", "NOCHE", "DIA",
    "PERRO", "GATO", "PAJARO", "PEZ", "CABALLO", "VACA", "OVEJA", "CABRA",
    "CERDO", "TORTUGA", "RANA", "ZORRO", "OSO", "LOBO", "LEON", "TIGRE",
    "ELEFANTE", "DELFIN", "MARIPOSA", "ABEJA",
    "CASA", "CIUDAD", "PUEBLO", "CAMPO", "CARRETERA", "PUENTE", "ISLA",
    "VALLE", "DESIERTO", "CASCADA", "VOLCAN", "JARDIN", "PARQUE", "PLAYA",
    "MESA", "SILLA", "CAMA", "PUERTA", "VENTANA", "LIBRO", "LAPIZ",
    "RELOJ", "LLAVE", "CELULAR", "BOLSA", "ZAPATO", "SOMBRERO", "PELOTA",
    "CAJA", "LINTERNA", "BOTELLA", "VASO", "PLATO", "TENEDOR",
]


class BingoCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    room = models.ForeignKey("Room", on_delete=models.CASCADE)
    words = models.JSONField()  # 25 palabras (5x5)

    @classmethod
    def generate_words(cls):
        return random.sample(WORDS, 25)

    def rows(self):
        w = self.words
        return [w[i * 5:(i + 1) * 5] for i in range(5)]


# ------------- FORMAS DE BINGO (5x5) -------------

BINGO_PATTERNS = {
    "linea_completa": {
        "label": "Cartón lleno",
        "cells": [(r, c) for r in range(5) for c in range(5)],
    },
    "t": {
        "label": "Forma T",
        "cells": (
            [(0, c) for c in range(5)] +      # fila superior
            [(r, 2) for r in range(1, 5)]     # columna central
        ),
    },
    "x": {
        "label": "Forma X",
        "cells": (
            [(i, i) for i in range(5)] +          # diagonal principal
            [(i, 4 - i) for i in range(5)]        # diagonal secundaria
        ),
    },
    "l": {
        "label": "Forma L",
        "cells": (
            [(r, 0) for r in range(5)] +          # primera columna
            [(4, c) for c in range(1, 5)]         # fila inferior
        ),
    },
}


class GameState(models.Model):
    room = models.OneToOneField("Room", on_delete=models.CASCADE)
    words_order = models.JSONField(default=list)
    called_words = models.JSONField(default=list)
    next_index = models.IntegerField(default=0)

    pattern = models.CharField(
        max_length=20,
        default="linea_completa",
        choices=[(k, v["label"]) for k, v in BINGO_PATTERNS.items()],
    )

    winner = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="won_bingos",
    )

    @classmethod
    def start_new_for_room(cls, room):
        game_state, _ = cls.objects.get_or_create(room=room)

        shuffled = WORDS.copy()
        random.shuffle(shuffled)
        game_state.words_order = shuffled
        game_state.called_words = []
        game_state.next_index = 0

        # forma aleatoria
        pattern_name = random.choice(list(BINGO_PATTERNS.keys()))
        game_state.pattern = pattern_name

        # al iniciar ronda, sin ganador
        game_state.winner = None

        game_state.save()
        return game_state

    def call_next(self):
        if self.next_index >= len(self.words_order):
            return None
        word = self.words_order[self.next_index]
        self.next_index += 1
        self.called_words.append(word)
        self.save()
        return word

    def check_bingo_for_card(self, card):
        """
        Devuelve True si ESTE cartón cumple la forma actual
        usando SOLO palabras ya cantadas.
        """
        pattern_def = BINGO_PATTERNS.get(self.pattern)
        if not pattern_def:
            return False

        coords = pattern_def["cells"]   # lista de (fila, col)
        words = card.words              # 25 palabras en lista
        called = set(self.called_words)

        for (r, c) in coords:
            idx = r * 5 + c
            if idx < 0 or idx >= len(words):
                return False
            if words[idx] not in called:
                return False

        return True
