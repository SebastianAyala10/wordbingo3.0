from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Room, BingoCard, GameState, BINGO_PATTERNS




from .models import Room, BingoCard, GameState


# Página de inicio (landing del bingo)
def home(request):
    return render(request, "bingo/home.html")


# Lobby al que se llega después de login/registro
@login_required
def lobby(request):
    return render(request, "bingo/lobby.html")


# Crear una sala nueva
@login_required
def create_room(request):
    if request.method == "POST":
        name = request.POST.get("name") or f"Sala de {request.user.username}"
        wait_seconds = 30  # puedes cambiarlo si quieres otro tiempo

        room = Room.objects.create(
            name=name,
            host=request.user,
            status="waiting",
            wait_end_time=timezone.now() + timedelta(seconds=wait_seconds),
        )
        room.players.add(request.user)
        return redirect("bingo:waiting_room", room_id=room.id)

    return render(request, "bingo/create_room.html")


# Listar salas disponibles para unirse
@login_required
def room_list(request):
    # Por simplicidad mostramos todas las salas que estén en "waiting"
    rooms = Room.objects.filter(status="waiting").order_by("-created_at")
    return render(request, "bingo/room_list.html", {"rooms": rooms})


@login_required
def waiting_room_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)

    if room.status == "running":
        return redirect("bingo:game", room_id=room.id)

    if room.status == "finished":
        room.status = "waiting"
        room.wait_end_time = timezone.now() + timedelta(seconds=30)
        room.players.clear()
        room.save()
        BingoCard.objects.filter(room=room).delete()
        GameState.objects.filter(room=room).delete()

    room.players.add(request.user)

    is_host = (request.user == room.host)   # 👈 IMPORTANTE

    return render(
        request,
        "bingo/waiting_room.html",
        {
            "room": room,
            "is_host": is_host,
        },
    )




# API que usa la sala de espera (contador + lista de jugadores)
@login_required
def room_status_api(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    remaining = room.remaining_seconds()
    players = list(room.players.values_list("username", flat=True))
    return JsonResponse(
        {"status": room.status, "remaining_seconds": remaining, "players": players}
    )




# Vista de la partida (cartón + UI del juego)
@login_required
def game_view(request, room_id):
    room = get_object_or_404(Room, pk=room_id)

    card, _ = BingoCard.objects.get_or_create(
        user=request.user,
        room=room,
        defaults={"words": BingoCard.generate_words()},
    )

    game_state, _ = GameState.objects.get_or_create(room=room)
    if not game_state.called_words:
        game_state.call_next()

    # 👇 obtengo label bonito de la forma
    from .models import BINGO_PATTERNS  # al inicio del archivo mejor
    pattern_label = BINGO_PATTERNS.get(game_state.pattern, {}).get("label", "Cartón lleno")

    return render(
        request,
        "bingo/game.html",
        {
            "room": room,
            "card": card,
            "game": game_state,
            "pattern_name": game_state.pattern,
            "pattern_label": pattern_label,
        },
    )



# API para que el front sepa palabra actual y lista de palabras
@login_required
def game_state_api(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    game_state, _ = GameState.objects.get_or_create(room=room)

    last_word = game_state.called_words[-1] if game_state.called_words else None
    winner_name = game_state.winner.username if game_state.winner else None

    return JsonResponse(
        {
            "status": room.status,
            "last_word": last_word,
            "called_words": game_state.called_words,
            "pattern": game_state.pattern,
            "winner": winner_name,
        }
    )


# API del botón "Siguiente palabra"
@login_required
@require_POST
def call_next_word(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    game_state, _ = GameState.objects.get_or_create(room=room)

    word = game_state.call_next()
    finished = word is None

    return JsonResponse(
        {
            "finished": finished,
            "word": word,
            "called_words": game_state.called_words,
        }
    )


# Marcar partida como terminada (para poder empezar una nueva ronda luego)
@login_required
def finish_game(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    room.status = "finished"
    room.save()
    return redirect("bingo:lobby")

@login_required
@require_POST
def start_game(request, room_id):
    room = get_object_or_404(Room, pk=room_id)

    # Solo el host puede iniciar
    if request.user != room.host:
        return JsonResponse({"error": "Solo el host puede iniciar la partida."}, status=403)

    if room.status != "waiting":
        return JsonResponse({"error": "La partida ya está en curso o ha terminado."}, status=400)

    # Cambiamos el estado a running
    room.status = "running"
    room.save()

    # Crear estado de juego nuevo
    game_state = GameState.start_new_for_room(room)

    # Crear cartones 5x5 para cada jugador
    for player in room.players.all():
        BingoCard.objects.get_or_create(
            user=player,
            room=room,
            defaults={"words": BingoCard.generate_words()},
        )

    # Asegurar primera palabra
    if not game_state.called_words:
        game_state.call_next()

    return JsonResponse({"ok": True})

@login_required
@require_POST
def claim_bingo(request, room_id):
    room = get_object_or_404(Room, pk=room_id)
    game_state, _ = GameState.objects.get_or_create(room=room)

    # Si ya hay ganador, no aceptar otro
    if game_state.winner is not None:
        return JsonResponse(
            {
                "ok": False,
                "error": "Ya hay un ganador.",
                "winner": game_state.winner.username,
            },
            status=400,
        )

    # Partida debe estar en curso
    if room.status != "running":
        return JsonResponse(
            {"ok": False, "error": "La partida no está en curso."},
            status=400,
        )

    # Cartón del usuario
    try:
        card = BingoCard.objects.get(room=room, user=request.user)
    except BingoCard.DoesNotExist:
        return JsonResponse(
            {"ok": False, "error": "No tienes cartón en esta sala."},
            status=400,
        )

    # Verificar forma
    if not game_state.check_bingo_for_card(card):
        return JsonResponse(
            {"ok": False, "error": "Todavía no cumples la forma de esta partida."},
            status=400,
        )

    # ✅ BINGO VÁLIDO
    game_state.winner = request.user
    game_state.save()

    room.status = "finished"
    room.save()

    return JsonResponse(
        {"ok": True, "winner": request.user.username},
        status=200,
    )


