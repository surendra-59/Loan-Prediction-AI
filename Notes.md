

---

## Notes (for Beginners)

### How to create virtual env

```
python -m venv myworld
```

Activate it:

* Windows: `myworld\Scripts\activate`
* Mac/Linux: `source myworld/bin/activate`

---

### How to create Django Project

```
django-admin startproject project_name
```

Go inside project folder:

```
cd project_name
```

---

### How to create Django App

```
python manage.py startapp members
```

* `members` is the app name, you can choose any name.
* Add it in `settings.py` under `INSTALLED_APPS`.

---

### How to run app
```
python manage.py runserver
```

---

### How Django handles URL requests

Suppose you enter URL:

```
http://127.0.0.1:8000/user-dashboard/
```

* Django first looks in `urls.py` to match the path:

```python
path("user-dashboard/", user_dashboard, name="user_dashboard")
```

* `"user-dashboard"` → what you see in browser
* `user_dashboard` → function inside `views.py` that runs
* `name="user_dashboard"` → URL name you can use inside templates (`{% url 'user_dashboard' %}`) or redirect

---

### Models and Database

* `models.py` → structure of database
* Create models for your app tables (e.g., Users, Bankers, Loan Applications)

When you create or change models:

```
python manage.py makemigrations
```

* `makemigrations` → creates migration files (like blueprint)
* `migrate` → actually creates tables in database:

```
python manage.py migrate
```

---

### Custom User Model (Email Login)

* By default, Django uses `username` for login.
* We can create **email-based login** by creating a custom user model:

```python
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
```

* Create a custom manager with `create_user` and `create_superuser`.
* Set `USERNAME_FIELD = 'email'` in model.
* Update `settings.py`:

```python
AUTH_USER_MODEL = 'app.CustomUser'
```

* Create superuser:

```
python manage.py createsuperuser
```

---

### Views (Handling Requests)

* `views.py` contains functions that run when a URL is accessed.

Example:

```python
def login_view(request):
    if request.method == "POST":
        # get data from HTML form
        email = request.POST.get("email")
        password = request.POST.get("password")
        # authenticate user
        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)
            return redirect("user_dashboard")
```

* `render(request, "template.html")` → displays template
* `redirect("url_name")` → goes to another URL

---

### Templates (HTML)

* Put HTML files in `templates` folder inside app.
* You can organize by folders like `user/` and `banker/`.
* Use `{% extends "user/base.html" %}` to reuse common HTML (like navbar).
* Use `{% block content %} {% endblock %}` for page-specific content.

---

### URLs

* Inside `app/urls.py`:

```python
from django.urls import path
from .views import login_view, user_dashboard

urlpatterns = [
    path("login/", login_view, name="login"),
    path("user-dashboard/", user_dashboard, name="user_dashboard"),
]
```

* Include app URLs in project `urls.py`:

```python
path('', include('app.urls'))
```

---

### Authentication and Roles

* You can protect pages using decorators:

```python
from django.contrib.auth.decorators import login_required
from .decorators import role_required

@login_required
@role_required(allowed_roles=["USER"])
def user_dashboard(request):
    ...
```

* `login_required` → ensures only logged-in users can see the page
* `role_required` → ensures only correct user type (USER/BANKER) can access

---

### Logout

```python
from django.contrib.auth import logout

def logout_view(request):
    logout(request)
    return redirect("login")
```

* Add a link in templates:

```html
<a href="{% url 'logout' %}">Logout</a>
```

---

### Redirect root URL `/`

* In `views.py`:

```python
def home(request):
    if request.user.is_authenticated:
        if request.user.user_type == "BANKER":
            return redirect("banker_dashboard")
        else:
            return redirect("user_dashboard")
    return redirect("login")
```

* Add in `urls.py`:

```python
path('', home, name='home')
```

---

### Using MySQL Database

1. Install package:

```
pip install mysqlclient
```

2. Create MySQL database:

```sql
CREATE DATABASE loan_prediction_db;
CREATE USER 'loan_user'@'localhost' IDENTIFIED BY 'password123';
GRANT ALL PRIVILEGES ON loan_prediction_db.* TO 'loan_user'@'localhost';
FLUSH PRIVILEGES;
```

3. Update `settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'loan_prediction_db',
        'USER': 'loan_user',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '3306',
    }
}
```

4. Run migrations:

```
python manage.py makemigrations
python manage.py migrate
```

---

### Moving Data from SQLite to MySQL

1. Dump SQLite data:

```
python manage.py dumpdata --exclude auth.permission --exclude contenttypes --exclude sessions > data.json
```

2. Load into MySQL:

```
python manage.py loaddata data.json
```

✅ Done! All your SQLite data is now in MySQL.

---

### Notes for Templates

* Use `{% url 'url_name' %}` instead of writing file paths
* Use `{% extends %}` and `{% block %}` to reuse HTML layouts
* Keep separate folders for **user** and **banker** templates

---


Perfect 😎 Let’s create a **simple flow diagram** for your Loan Prediction app, in a way a beginner can understand. I’ll write it in text form so it can be included in your notes, and later they can draw it if they want.

---

### Loan Prediction System – Request Flow Diagram

```
[Browser URL]
       |
       v
-------------------
|  Django urls.py |
-------------------
  | path matches
  v
-------------------
|    Views.py     |
-------------------
  | Handles request:
  | - Gets form data (POST/GET)
  | - Authenticates user / creates user
  | - Calls database via Models
  | - Decides template or redirect
  v
-------------------
|   Models.py     |
-------------------
  | - Represents database tables
  | - CustomUser table stores users/bankers
  | - LoanApplication table stores loans
  v
-------------------
| Database (MySQL)|
-------------------
  | - Stores all data
  | - Django ORM reads/writes here
  v
-------------------
| Templates (HTML)|
-------------------
  | - user/user_dashboard.html
  | - banker/banker_dashboard.html
  | - login.html / register.html
  | - base.html for shared layout
       |
       v
[Browser Displays HTML Page]
```

---

### Step-by-Step Flow (Example: User Login)

1. User opens browser → goes to `/login/`
2. Django checks `urls.py` → maps to `login_view` in `views.py`
3. `login_view` checks if user exists in **CustomUser** table via `authenticate()`
4. If valid:

   * Logs in user → `login()` function
   * Redirects to `/user-dashboard/` or `/banker-dashboard/` based on `user_type`
5. `user_dashboard` view calls `render()` → renders template `user/user_dashboard.html`
6. Template shows user-specific info, navbar, logout link
7. Browser displays final HTML page

---

### Step-by-Step Flow (Example: User Registration)

1. User goes to `/register/`
2. Django maps URL → `register_view` in `views.py`
3. `register_view`:

   * Reads form data (Full Name, Email, Phone, Password, Terms)
   * Validates inputs
   * Creates user using `CustomUser.objects.create_user()`
4. Redirects user to `/login/`
5. User can now login using email/password

---

### Optional Notes for Teammates

* `@login_required` ensures pages are visible **only to logged-in users**
* `role_required` ensures pages are visible only to **correct user type**
* Templates use `{% extends %}` & `{% block %}` for reusable layouts
* Always use `{% url 'url_name' %}` instead of hardcoding paths

---


### Perfect 😎 Let’s make a **visual ASCII diagram showing separate flows for User vs Banker** so it’s super beginner-friendly.

---

### Loan Prediction App – User vs Banker Flow

```
                      [Browser]
                          |
                          v
                        /login/
                          |
                          v
                    Django urls.py
                          |
       ---------------------------------------
       |                                     |
user_type = "USER"                     user_type = "BANKER"
       |                                     |
       v                                     v
-------------------                  -------------------
| login_view()    |                  | login_view()    |
-------------------                  -------------------
       |                                     |
authenticate()                            authenticate()
       |                                     |
login(request, user)                     login(request, user)
       |                                     |
redirect("user_dashboard")                redirect("banker_dashboard")
       |                                     |
       v                                     v
-------------------                  -------------------
| user_dashboard  |                  | banker_dashboard|
-------------------                  -------------------
       |                                     |
render("user/user_dashboard.html")        render("banker/banker_dashboard.html")
       |                                     |
display navbar, logout,                  display navbar, logout,
loan info, etc                           banker controls, etc
       |                                     |
       v                                     v
     [Browser Displays HTML Page]
```

---

### Optional Notes for Teammates:

* The **same login view** handles both user and banker; the `user_type` determines the redirect.
* Dashboards are separate templates (`user/` vs `banker/`) for clear separation.
* Logout works for both user types and redirects to `/login/`.
* Role protection ensures **users cannot access banker pages** and vice versa.

---


### Let’s create a **full system overview diagram** for your Loan Prediction app. This will show **all major flows: Registration → Login → Dashboard → Loan Application → Admin → MySQL**. It’s beginner-friendly and shows the “big picture”.

---

### Loan Prediction App – Full System Overview

```
                         [Browser]
                              |
             -----------------------------------
             |                                 |
          /register/                         /login/
             |                                 |
     Django urls.py                       Django urls.py
             |                                 |
      register_view()                      login_view()
             |                                 |
  Validate form & Terms?                authenticate(email,password)
             |                                 |
      Create CustomUser                   Check user_type
             |                                 |
      redirect("login")                -------------------------
                                        |                       |
                                  user_type = USER        user_type = BANKER
                                        |                       |
                                redirect("user_dashboard")  redirect("banker_dashboard")
                                        |                       |
                            ------------------------   ------------------------
                            | user_dashboard.html |   | banker_dashboard.html |
                            ------------------------   ------------------------
                                        |                       |
                  Displays user info, loan form, etc   Displays banker controls
                                        |                       |
                                Submit loan request          Approve/Reject loans
                                        |                       |
                          ---------------------------         |
                          | LoanApplication Model |         |
                          ---------------------------       |
                                        |                   |
                                ORM writes/reads MySQL tables
                                        |
                           ---------------------------
                           |      MySQL Database      |
                           ---------------------------
                        Stores Users, Bankers, Loans

```

---

### Beginner-Friendly Notes:

1. **Registration:**

   * Only for **users**. Bankers are created via **Admin (superuser)**.
2. **Login:**

   * Email-based authentication using `CustomUser`.
   * Role determines which dashboard they see.
3. **Dashboards:**

   * `user_dashboard` → submit/view loans
   * `banker_dashboard` → approve/reject/view users’ loans
4. **Loan Application Model:**

   * Django model that stores loan data in MySQL.
5. **Admin Panel:**

   * Superuser can create bankers, see all users, and manage data.
6. **MySQL Database:**

   * Stores all data: users, bankers, loan applications.

---


