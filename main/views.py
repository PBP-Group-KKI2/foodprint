from django.shortcuts import render
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
import datetime
from django.contrib import messages

<<<<<<< HEAD

def show_landing(request):
    return render(request, 'landing_page.html')
=======
# Create your views here.
def show_landing(request):
    last_login = request.COOKIES.get('last_login', 'No active login session / Cookie not found')
    context = {
        "last_login": last_login,
    }
    return render(request, 'landing_page.html', context)

#ordinary user register an account
def register(request):
    form = UserCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account created successfully. Please log in.")
        return redirect("main:login")

    context = {
        "name": "FoodPrint",
        "form": form,
    }
    return render(request, "register.html", context)

#login function
def login_user(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        response = redirect("main:show_main")
        response.set_cookie('last_login', datetime.datetime.now().strftime('%d-%m %Y [%H:%M:%S]'))
        return response

    context = {
        "name": "Foodprint",
        "form": form,
    }
    return render(request, "login.html", context)

#logout function
def logout_user(request):
    logout(request)
    response = redirect("main:show_main")
    response.delete_cookie('last_login')
    return redirect("main:show_main")

#for future use, mainly serve as a yurisdiction of editor
def is_editor(user):
    return user.groups.filter(name='Editor').exists()
>>>>>>> b56c1f0 (feat: authorization on landing_page,views,and urls)
