from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages


def login_view(request):
    """Pantalla de inicio de sesión."""
    if request.user.is_authenticated:
        return redirect("bingo:lobby")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("bingo:lobby")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "accounts/login.html")


def register_view(request):
    """Pantalla de registro usando el UserCreationForm de Django."""
    if request.user.is_authenticated:
        return redirect("bingo:lobby")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # iniciar sesión automáticamente después de registrarse
            login(request, user)
            return redirect("bingo:lobby")
    else:
        form = UserCreationForm()

    # adaptamos el formulario a nuestros inputs manuales
    # si quieres usar tus propios <input>, simplemente tomas
    # request.POST['username'], password1, password2 y creas el User a mano.
    context = {"form": form}
    return render(request, "accounts/register.html", context)


def logout_view(request):
    """Cierra la sesión y vuelve al home."""
    logout(request)
    return redirect("home")
