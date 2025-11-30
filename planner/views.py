import os
import threading

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseNotFound
from django.shortcuts import redirect, render
from io import BytesIO

from .documents import ingest_document
from .forms import UploadForm
from .models import Plan
from .agents import create_plan


DEV_MODE = os.getenv("DEV_MODE") == "true"


def index(request):
    if request.user.is_authenticated:
        return redirect(to="/plans")

    if request.method == "GET":
        return render(request, "index.html.tmpl", {"dev_mode": DEV_MODE})
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
        return render(request, "register.html.tmpl", {"dev_mode": DEV_MODE})
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
    if request.method == "GET":
        return render(request, "plans/new.html.tmpl", {"dev_mode": DEV_MODE})
    elif request.method == "POST":
        prompt = request.POST["prompt"]
        threading.Thread(
            target=create_plan,
            args=(prompt, request.user),
            daemon=True,
        ).start()
        return redirect(to="/plans/processing")

    return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])


@login_required(login_url="/")
def plan_processing(request):
    return render(request, "plans/processing.html.tmpl", {"dev_mode": DEV_MODE})


@login_required(login_url="/")
def plan_list(request):
    plans = Plan.objects.order_by(
        "-created_at").filter(user=request.user)  # type:ignore
    return render(request, "plans/list.html.tmpl", {"dev_mode": DEV_MODE, "plans": plans})


@login_required(login_url="/")
def plan_detail(request, plan_id):
    plan = Plan.objects.get(pk=plan_id, user=request.user)  # type:ignore
    if plan is None:
        return HttpResponseNotFound(b"Plan not found")
    return render(request, "plans/detail.html.tmpl", {"dev_mode": DEV_MODE, "plan": plan})


@staff_member_required(login_url="/")
def document_new(request):
    if request.method == "GET":
        return render(request, "documents/new.html.tmpl", {"dev_mode": DEV_MODE})
    elif request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if not form.is_valid():
            return HttpResponseBadRequest(content=b"Invalid form.")

        name = form.cleaned_data["name"]
        document = form.cleaned_data["document"]
        body = BytesIO(document.read())
        document.close()

        threading.Thread(
            target=ingest_document,
            args=(name, body),
            daemon=True,
        ).start()

        return redirect(to="/documents/processing")

    return HttpResponseNotAllowed(permitted_methods=["GET", "POST"])


@staff_member_required(login_url="/")
def document_processing(request):
    return render(request, "documents/processing.html.tmpl", {"dev_mode": DEV_MODE})
