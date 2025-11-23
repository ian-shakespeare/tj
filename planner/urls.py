from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.register, name="register"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("plans/", views.plan_list, name="plan_list"),
    path("plans/<int:plan_id>/", views.plan_detail, name="plan_detail"),
    path("plans/new/", views.plan_new, name="plan_new"),
]
