import os

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound
from django.shortcuts import redirect, render


DEV_MODE = os.getenv("DEV_MODE") == "true"


def index(request):
    if request.user.is_authenticated:
        return redirect(to="/plans")

    if request.method == "GET":
        return render(request, template_name="index.html.tmpl", context={"dev_mode": DEV_MODE})
    elif request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            return HttpResponseNotFound(content=b"User not found.")

        login(request, user)
        return redirect(to="/plans")

    return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])


def register(request):
    if request.user.is_authenticated:
        return redirect(to="/plans")

    if request.method == "GET":
        return render(request, template_name="register.html.tmpl", context={"dev_mode": DEV_MODE})
    elif request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]
        password = request.POST["password"]

        new_user = User.objects.create_user(username, email, password)
        new_user.save()

        user = authenticate(request, username=username, password=password)
        if user is None:
            return HttpResponseNotFound(content=b"User not found.")

        login(request, user)
        return redirect(to="/plans")

    return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])


@login_required(login_url="/")
def sign_out(request):
    logout(request)
    return redirect(to="/")


@login_required(login_url="/")
def plan_new(request):
    return HttpResponse(b"Plan New")


@login_required(login_url="/")
def plan_list(request):
    return HttpResponse(b"Plan List")


@login_required(login_url="/")
def plan_detail(request, plan_id):
    return HttpResponse(b"Plan Detail")
